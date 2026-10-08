#!/usr/bin/env python3
"""Compare the same ICU4X adapter from native Rust and C++ through Crubit."""
import argparse
import hashlib
import json
import random
import statistics
import subprocess
from pathlib import Path

from benchmark import ROOT, build_metadata, cache_values, make_names, positive, run


def make_pairs(dataset, count, seed):
    if dataset == "short-ascii":
        choices = [("a", "b"), ("same", "same"), ("z", "a"), ("", "x")]
        return [choices[i % len(choices)] for i in range(count)]
    names = make_names(dataset, count + 1, seed)
    nearby = sorted(names)
    rng = random.Random(seed + 1)
    # Include both unrelated strings and strings with long common prefixes.
    return [(nearby[i], nearby[i + 1]) if i % 2 else
            (names[i], names[rng.randrange(len(names))]) for i in range(count)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build-release")
    parser.add_argument("--pairs", type=positive, default=10000)
    parser.add_argument("--iterations", type=positive, default=100)
    parser.add_argument("--samples", type=positive, default=9)
    parser.add_argument("--seed", type=int, default=30535)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    build = args.build_dir.resolve()
    cache = cache_values(build)
    target = build / "native-rust"
    subprocess.run(["cargo", "+" + cache["Rust_TOOLCHAIN"], "build", "--release",
                    "--locked", "--offline", "--manifest-path", str(ROOT / "rust/Cargo.toml"),
                    "--example", "compare_pairs", "--target-dir", str(target)], check=True)
    native = target / "release/examples/compare_pairs"
    report = {**build_metadata(build, cache), "pairs": args.pairs,
              "iterations": args.iterations, "samples": args.samples,
              "seed": args.seed, "results": []}
    print(f"{args.pairs:,} pairs; {args.iterations} repetitions; {args.samples} samples/path", flush=True)
    print(f"{'Workload':28} {'Rust ns/pair':>14} {'Crubit ns/pair':>16} {'Crubit/Rust':>13}", flush=True)
    for dataset, locale in [("short-ascii", "en-US"), ("latin", "en-US"),
                            ("latin", "de-u-co-phonebk"), ("japanese", "ja"), ("chinese", "zh")]:
        pairs = make_pairs(dataset, args.pairs, args.seed)
        stdin = "".join(left + "\n" + right + "\n" for left, right in pairs)
        rows = {"native-rust": [], "crubit": []}
        expected = None
        for sample in range(args.samples):
            order = ("native-rust", "crubit") if sample % 2 == 0 else ("crubit", "native-rust")
            for backend in order:
                if backend == "native-rust":
                    output = subprocess.run([str(native), locale, str(args.iterations)],
                                            input=stdin, capture_output=True, encoding="utf-8",
                                            check=True, timeout=120).stdout
                else:
                    output = run(build, "icu4x-demo", "--locale", locale, "--stdin",
                                 "--benchmark-pairs", str(args.iterations), stdin=stdin)
                result = json.loads(output)
                signature = (result["warmup_checksum"], result["checksum"])
                if expected is None:
                    expected = signature
                if (signature != expected or result["pairs"] != args.pairs or
                        result["iterations"] != args.iterations or result["compare_ns"] <= 0):
                    raise RuntimeError(f"Invalid or inconsistent {backend} result: {result}")
                rows[backend].append(result)
        summary = {}
        for backend, samples in rows.items():
            times = [row["compare_ns"] / (args.pairs * args.iterations) for row in samples]
            summary[backend] = {"median_ns_per_pair": statistics.median(times),
                                "min_ns_per_pair": min(times), "max_ns_per_pair": max(times)}
        rust = summary["native-rust"]["median_ns_per_pair"]
        crubit = summary["crubit"]["median_ns_per_pair"]
        report["results"].append({"dataset": dataset, "locale": locale,
            "input_sha256": hashlib.sha256(stdin.encode("utf-8")).hexdigest(),
            "summary": summary, "crubit_over_rust": crubit / rust, "raw_samples": rows})
        print(f"{dataset + ' / ' + locale:28} {rust:14.2f} {crubit:16.2f} {crubit / rust:13.3f}", flush=True)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"Saved {args.json}")


if __name__ == "__main__":
    main()
