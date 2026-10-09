#!/usr/bin/env python3
"""Compare the same ICU4X adapter from native Rust and C++ through Crubit."""
import argparse
import hashlib
import json
import platform
import random
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


WORDS = ("Andersson", "Åberg", "Angstrom", "Berg", "Björk", "Chen", "Cheng",
         "Garcia", "García", "Hansen", "Ibrahim", "Ivanov", "Jensen", "Kim",
         "Kowalski", "Lindberg", "Martin", "Meyer", "Mueller", "Müller",
         "Nguyen", "Öberg", "Özil", "Petrov", "Rossi", "Sato", "Schmidt",
         "Silva", "Smith", "Sørensen", "Wang", "Zimmermann")


CORPORA = {
    "latin": WORDS,
    "japanese": ("佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村",
                 "小林", "加藤", "吉田", "山田", "佐々木", "山口", "松本", "井上",
                 "木村", "林", "斎藤", "清水", "山崎", "森", "池田", "橋本",
                 "石川", "阿部", "石井", "長谷川", "さくら", "ひなた", "ハル", "ミナ"),
    "chinese": ("王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴", "徐",
                "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗", "梁", "宋",
                "郑", "谢", "韩", "唐", "冯", "于", "董", "萧", "程", "曹"),
}


def make_names(dataset, count, seed):
    rng = random.Random(seed)
    words = CORPORA[dataset]
    return [f"{rng.choice(words)} {rng.choice(words)} {rng.randrange(100000):05d}"
            for _ in range(count)]


def positive(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def cache_values(build):
    values = {}
    for line in (build / "CMakeCache.txt").read_text().splitlines():
        if line and not line.startswith(("#", "//")) and "=" in line:
            key, value = line.split("=", 1)
            values[key.split(":", 1)[0]] = value
    if values.get("CMAKE_BUILD_TYPE") != "Release" or values.get("ENABLE_ASAN") != "OFF":
        raise RuntimeError("Use a separate build with -DCMAKE_BUILD_TYPE=Release -DENABLE_ASAN=OFF")
    return values


def run(build, backend, *args, stdin=""):
    return subprocess.run([str(build / backend), *args], input=stdin,
                          capture_output=True, encoding="utf-8", check=True,
                          timeout=120).stdout


def command_line(*args):
    return subprocess.check_output(args, text=True).strip()


def build_metadata(build, cache):
    report = {
        "platform": platform.platform(), "machine": platform.machine(),
        "compiler": command_line(cache["CMAKE_CXX_COMPILER"], "--version").splitlines()[0],
        "rustc": command_line("rustup", "run", cache["Rust_TOOLCHAIN"], "rustc", "-V"),
        "versions": {"icu4x-demo": run(build, "icu4x-demo", "--version").strip()},
        "build_type": cache["CMAKE_BUILD_TYPE"], "asan": False,
    }
    if platform.system() == "Darwin":
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                             capture_output=True, text=True)
        if cpu.returncode == 0:
            report["cpu"] = cpu.stdout.strip()
    return report


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
              "seed": args.seed,
              "paths": {"native-rust": "Rust calls locale_collator::Collator directly",
                        "crubit": "C++ calls the same adapter through Crubit"},
              "results": []}
    print(f"{args.pairs:,} pairs; {args.iterations} repetitions; {args.samples} samples/path", flush=True)
    print(f"{'Workload':28} {'Rust adapter ns/pair':>20} {'C++ via Crubit ns/pair':>22} {'Crubit/Rust':>13}", flush=True)
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
        print(f"{dataset + ' / ' + locale:28} {rust:20.2f} {crubit:22.2f} {crubit / rust:13.3f}", flush=True)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"Saved {args.json}")


if __name__ == "__main__":
    main()
