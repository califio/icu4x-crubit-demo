#!/usr/bin/env python3
"""Compare peak resident memory of the two ordinary demo CLI processes."""
import argparse
import hashlib
import json
import os
import platform
import statistics
import tempfile
from pathlib import Path

from benchmark import (BACKENDS, CORPORA, DEFAULT_LOCALES, ROOT, build_metadata,
                       cache_values, make_names, positive)

MIB = 1024 * 1024


def nonnegative(value):
    value = int(value)
    if value < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return value


def measure(build, backend, arguments, stdin):
    # wait4 reports this child's high-water mark, not the Python runner's
    # memory or the cumulative maximum across previously reaped children.
    with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as output, \
            tempfile.TemporaryFile() as errors:
        source.write(stdin)
        source.seek(0)
        executable = str(build / backend)
        actions = [(os.POSIX_SPAWN_DUP2, source.fileno(), 0),
                   (os.POSIX_SPAWN_DUP2, output.fileno(), 1),
                   (os.POSIX_SPAWN_DUP2, errors.fileno(), 2)]
        pid = os.posix_spawn(executable, [executable, *arguments],
                             os.environ.copy(), file_actions=actions)
        _, status, usage = os.wait4(pid, 0)
        output.seek(0)
        errors.seek(0)
        stdout, stderr = output.read(), errors.read()
    exit_code = os.waitstatus_to_exitcode(status)
    if exit_code != 0:
        raise RuntimeError(f"{backend} exited with {exit_code}: "
                           f"{stderr.decode('utf-8', errors='replace')}")
    # Darwin reports bytes; Linux reports KiB.
    peak_bytes = int(usage.ru_maxrss) * (1 if platform.system() == "Darwin" else 1024)
    if peak_bytes <= 0:
        raise RuntimeError(f"Invalid peak RSS from {backend}: {usage.ru_maxrss}")
    return stdout, {"peak_rss_bytes": peak_bytes,
                    "user_seconds": usage.ru_utime,
                    "system_seconds": usage.ru_stime}


def summarize(samples):
    summary = {}
    for backend, rows in samples.items():
        values = [row["peak_rss_bytes"] for row in rows]
        summary[backend] = {"median_peak_rss_bytes": statistics.median(values),
                            "min_peak_rss_bytes": min(values),
                            "max_peak_rss_bytes": max(values)}
    return summary


def collect(build, arguments, stdin, count, expected=None):
    samples = {backend: [] for backend in BACKENDS}
    for index in range(count):
        for backend in BACKENDS[::1 if index % 2 == 0 else -1]:
            stdout, result = measure(build, backend, arguments, stdin)
            if expected is not None and stdout != expected:
                raise RuntimeError(f"Unexpected sorting output from {backend}")
            samples[backend].append(result)
    summary = summarize(samples)
    ratio = (summary[BACKENDS[0]]["median_peak_rss_bytes"] /
             summary[BACKENDS[1]]["median_peak_rss_bytes"])
    return {"summary": summary, "icu4c_over_icu4x": ratio,
            "raw_samples": samples}


def print_result(label, result):
    summary = result["summary"]
    print(f"{label:39} {summary[BACKENDS[0]]['median_peak_rss_bytes'] / MIB:12.3f} "
          f"{summary[BACKENDS[1]]['median_peak_rss_bytes'] / MIB:12.3f} "
          f"{result['icu4c_over_icu4x']:8.2f}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build-release")
    parser.add_argument("--words", type=nonnegative, action="append",
                        help="Repeat for multiple sizes (default: 0, 10000, 100000)")
    parser.add_argument("--samples", type=positive, default=7)
    parser.add_argument("--seed", type=int, default=30535)
    parser.add_argument("--dataset", choices=CORPORA, default="latin")
    parser.add_argument("--locale", action="append", help="Repeat to select locales")
    parser.add_argument("--json", type=Path, help="Save metadata and raw samples")
    args = parser.parse_args()
    if platform.system() not in ("Darwin", "Linux"):
        parser.error("This runner supports macOS and Linux")
    build = args.build_dir.resolve()
    sizes = args.words if args.words is not None else [0, 10000, 100000]
    report = {**build_metadata(build, cache_values(build)),
              "metric": "per-process peak resident set size",
              "measurement": "os.posix_spawn and os.wait4, ru_maxrss",
              "units": "bytes", "dataset": args.dataset, "seed": args.seed,
              "word_counts": sizes, "samples": args.samples, "results": []}
    print(f"{report.get('cpu', report['machine'])}; {report['compiler']}", flush=True)
    print(f"Ordinary CLI runs; {args.samples} fresh processes/backend/case", flush=True)
    print("Peak RSS includes process startup, input, collator, sort, and output.", flush=True)
    print(f"{'Workload':39} {'ICU4C MiB':>12} {'ICU4X MiB':>12} {'4C/4X':>8}", flush=True)
    report["startup"] = collect(build, ["--version"], b"", args.samples)
    print_result("--version (startup)", report["startup"])
    for words in sizes:
        names = make_names(args.dataset, words, args.seed)
        stdin = ("".join(name + "\n" for name in names)).encode("utf-8")
        input_hash = hashlib.sha256(stdin).hexdigest()
        for locale in args.locale or DEFAULT_LOCALES[args.dataset]:
            arguments = ["--locale", locale, "--stdin"]
            expected, _ = measure(build, BACKENDS[0], arguments, stdin)
            other, _ = measure(build, BACKENDS[1], arguments, stdin)
            if (other != expected or
                    sorted(expected.decode("utf-8").splitlines()) != sorted(names)):
                raise RuntimeError(f"Sorting results differ for {locale}; "
                                   "no comparable memory result reported")
            result = collect(build, arguments, stdin, args.samples, expected)
            report["results"].append({"locale": locale, "words": words,
                                      "input_sha256": input_hash, **result})
            print_result(f"{locale}, {words:,} names", result)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"Saved {args.json}")


if __name__ == "__main__":
    main()
