#!/usr/bin/env python3
"""Compare repeated ICU4C and ICU4X sorts in an unsanitized Release build."""
import argparse
import hashlib
import json
import platform
import random
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKENDS = ("icu4c-demo", "icu4x-demo")
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
DEFAULT_LOCALES = {"latin": ["en-US", "de@collation=phonebook", "sv"],
                   "japanese": ["ja"], "chinese": ["zh"]}


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


def checksum(names):
    value = 14695981039346656037
    for name in names:
        data = name.encode("utf-8")
        for byte in len(data).to_bytes(8, "little") + data:
            value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return value


def command_line(*args):
    return subprocess.check_output(args, text=True).strip()


def build_metadata(build, cache):
    report = {
        "platform": platform.platform(), "machine": platform.machine(),
        "compiler": command_line(cache["CMAKE_CXX_COMPILER"], "--version").splitlines()[0],
        "rustc": command_line("rustup", "run", cache["Rust_TOOLCHAIN"], "rustc", "-V"),
        "versions": {b: run(build, b, "--version").strip() for b in BACKENDS},
        "build_type": cache["CMAKE_BUILD_TYPE"], "asan": False,
    }
    if platform.system() == "Darwin":
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                             capture_output=True, text=True)
        if cpu.returncode == 0:
            report["cpu"] = cpu.stdout.strip()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build-release")
    parser.add_argument("--words", type=positive, default=10000)
    parser.add_argument("--iterations", type=positive, default=20)
    parser.add_argument("--samples", type=positive, default=7)
    parser.add_argument("--seed", type=int, default=30535)
    parser.add_argument("--dataset", choices=CORPORA, default="latin")
    parser.add_argument("--locale", action="append", help="Repeat to select locales")
    parser.add_argument("--json", type=Path, help="Save metadata and raw samples")
    args = parser.parse_args()
    build = args.build_dir.resolve()
    cache = cache_values(build)
    names = make_names(args.dataset, args.words, args.seed)
    stdin = "\n".join(names) + "\n"
    report = {
        **build_metadata(build, cache), "dataset": args.dataset,
        "seed": args.seed, "words": args.words, "iterations": args.iterations,
        "samples": args.samples,
        "input_sha256": hashlib.sha256(stdin.encode("utf-8")).hexdigest(),
        "results": [],
    }
    print(f"{report.get('cpu', report['machine'])}; {report['compiler']}", flush=True)
    print(f"{args.words:,} names; {args.iterations} sorts/sample; {args.samples} samples/backend", flush=True)
    print("Times exclude input, copying the unsorted list, and output. Setup is reported separately.", flush=True)
    print(f"{'Locale':28} {'ICU4C ms/sort':>15} {'ICU4X ms/sort':>15} {'4C/4X':>8}", flush=True)
    for locale in args.locale or DEFAULT_LOCALES[args.dataset]:
        ordered = [run(build, b, "--locale", locale, "--stdin", stdin=stdin).splitlines()
                   for b in BACKENDS]
        if ordered[0] != ordered[1] or sorted(ordered[0]) != sorted(names):
            raise RuntimeError(f"Sorting results differ for {locale}; no comparable timing reported")
        expected = checksum(ordered[0])
        samples = {b: [] for b in BACKENDS}
        for sample in range(args.samples):
            for backend in BACKENDS[::1 if sample % 2 == 0 else -1]:
                result = json.loads(run(build, backend, "--locale", locale, "--stdin",
                                        "--benchmark", str(args.iterations), stdin=stdin))
                if (result["checksum"] != expected or result["names"] != len(names)
                        or result["iterations"] != args.iterations or result["sort_ns"] <= 0):
                    raise RuntimeError(f"Invalid benchmark result from {backend}: {result}")
                samples[backend].append(result)
        summary = {}
        for backend, rows in samples.items():
            times = [row["sort_ns"] / args.iterations / 1e6 for row in rows]
            summary[backend] = {"median_ms_per_sort": statistics.median(times),
                                "min_ms_per_sort": min(times), "max_ms_per_sort": max(times),
                                "median_setup_ms": statistics.median(row["setup_ns"] for row in rows) / 1e6}
        ratio = summary[BACKENDS[0]]["median_ms_per_sort"] / summary[BACKENDS[1]]["median_ms_per_sort"]
        report["results"].append({"locale": locale, "summary": summary,
                                  "icu4c_over_icu4x": ratio, "raw_samples": samples})
        print(f"{locale:28} {summary[BACKENDS[0]]['median_ms_per_sort']:15.3f} "
              f"{summary[BACKENDS[1]]['median_ms_per_sort']:15.3f} {ratio:8.2f}", flush=True)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"Saved {args.json}")


if __name__ == "__main__":
    main()
