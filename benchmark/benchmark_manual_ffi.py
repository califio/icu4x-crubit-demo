#!/usr/bin/env python3
"""Compare handwritten C FFI and Crubit bindings to the same ICU4X adapter."""
import argparse
import hashlib
import json
import os
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


def integration_code():
    groups = {
        "common": ["rust/lib.rs", "benchmark/collator_error.h"],
        "manual": ["benchmark/manual_ffi.rs", "benchmark/manual_ffi.h",
                   "benchmark/manual_collator.h"],
        "crubit": ["collation.h", "benchmark/crubit_collator.h"],
    }
    report = {"counting_rule": "Nonblank lines excluding full-line // comments; "
              "build files, generated output, and shared timing code excluded"}
    for group, names in groups.items():
        files = {name: sum(bool(line.strip()) and not line.lstrip().startswith("//")
                           for line in (ROOT / name).read_text().splitlines())
                 for name in names}
        report[group] = {"files": files, "total_lines": sum(files.values())}
    return report


def timing_summary(samples, field, count):
    times = [sample[field] / count for sample in samples]
    return {"median_ns": statistics.median(times), "min_ns": min(times), "max_ns": max(times)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build-release")
    parser.add_argument("--pairs", type=positive, default=10000)
    parser.add_argument("--iterations", type=positive, default=100)
    parser.add_argument("--lifecycle-iterations", type=positive, default=1000)
    parser.add_argument("--samples", type=positive, default=9)
    parser.add_argument("--seed", type=int, default=30535)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    build = args.build_dir.resolve()
    cache = cache_values(build)
    subprocess.run(["cmake", "--build", str(build), "--target", "ffi-bench", "icu4x-demo",
                    "--parallel", "8"], check=True,
                   env={**os.environ, "CARGO_NET_OFFLINE": "true"})
    binary = "benchmark/ffi-bench"
    print(run(build, binary, "--self-test").strip(), flush=True)
    report = {**build_metadata(build, cache), "pairs": args.pairs,
              "iterations": args.iterations, "lifecycle_iterations": args.lifecycle_iterations,
              "samples": args.samples, "seed": args.seed,
              "paths": {"manual": "C++ RAII owner calls the adapter through handwritten C FFI",
                        "crubit": "C++ owner calls the same compiled adapter through Crubit"},
              "adapter_artifact": json.loads((build / "benchmark/libmanual_ffi.json").read_text()),
              "integration_code": integration_code(), "results": []}
    print(f"{args.pairs:,} pairs × {args.iterations} repetitions; "
          f"{args.lifecycle_iterations:,} lifecycle iterations; {args.samples} paired samples", flush=True)
    print(f"{'Workload':28} {'Manual ns/pair':>15} {'Crubit ns/pair':>15} {'Ratio':>7} "
          f"{'Manual ns/cycle':>16} {'Crubit ns/cycle':>16} {'Ratio':>7}", flush=True)
    for dataset, locale in [("short-ascii", "en-US"), ("latin", "en-US"),
                            ("latin", "de-u-co-phonebk"), ("japanese", "ja"), ("chinese", "zh")]:
        pairs = make_pairs(dataset, args.pairs, args.seed)
        stdin = "".join(left + "\n" + right + "\n" for left, right in pairs)
        rows = {"manual": [], "crubit": []}
        orders = []
        expected = None
        for sample in range(args.samples):
            order = "manual-first" if sample % 2 == 0 else "crubit-first"
            result = json.loads(run(build, binary, order, locale, str(args.iterations),
                                    str(args.lifecycle_iterations), stdin=stdin))
            if (result["pairs"] != args.pairs or result["iterations"] != args.iterations or
                    result["lifecycle_iterations"] != args.lifecycle_iterations):
                raise RuntimeError(f"Invalid benchmark dimensions: {result}")
            orders.append(order)
            for backend in rows:
                row = result[backend]
                signature = tuple(row[key] for key in ("warmup_checksum", "checksum",
                                  "lifecycle_warmup_checksum", "lifecycle_checksum"))
                if expected is None:
                    expected = signature
                if signature != expected or row["compare_ns"] <= 0 or row["lifecycle_ns"] <= 0:
                    raise RuntimeError(f"Invalid or inconsistent {backend} result: {row}")
                rows[backend].append(row)
        summary = {backend: {
            "comparison": timing_summary(samples, "compare_ns", args.pairs * args.iterations),
            "lifecycle": timing_summary(samples, "lifecycle_ns", args.lifecycle_iterations),
        } for backend, samples in rows.items()}
        ratios = {metric: summary["crubit"][metric]["median_ns"] /
                          summary["manual"][metric]["median_ns"]
                  for metric in ("comparison", "lifecycle")}
        report["results"].append({"dataset": dataset, "locale": locale,
            "input_sha256": hashlib.sha256(stdin.encode("utf-8")).hexdigest(),
            "summary": summary, "crubit_over_manual": ratios,
            "sample_order": orders, "raw_samples": rows})
        m, c = summary["manual"], summary["crubit"]
        print(f"{dataset + ' / ' + locale:28} {m['comparison']['median_ns']:15.2f} "
              f"{c['comparison']['median_ns']:15.2f} {ratios['comparison']:7.3f} "
              f"{m['lifecycle']['median_ns']:16.2f} {c['lifecycle']['median_ns']:16.2f} "
              f"{ratios['lifecycle']:7.3f}", flush=True)
    code = report["integration_code"]
    print(f"Handwritten integration: manual FFI {code['manual']['total_lines']} lines; "
          f"Crubit {code['crubit']['total_lines']} lines; "
          f"shared {code['common']['total_lines']} lines", flush=True)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"Saved {args.json}")


if __name__ == "__main__":
    main()
