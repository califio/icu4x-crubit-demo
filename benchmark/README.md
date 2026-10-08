# Benchmarks

Run these commands from the repository root.

The main performance question is how much the generated binding adds to an
ICU4X call. Use a separate optimized build and run the fixed-pair benchmark:

```sh
cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release -DENABLE_ASAN=OFF \
  -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
cmake --build build-release --parallel 8
python3 benchmark/benchmark_bindings.py --json benchmark/benchmark-results-bindings.json
```

The runner builds a native Rust example with the same compiler and locked
dependencies. It compares the same ICU4X adapter called directly from Rust and
through Crubit from C++. Both loops reuse one collator, consume identical pairs,
and compute matching checksums. Each sample compares 10,000 pairs 100 times;
the runner alternates the execution order and reports medians from nine samples.
The native loop uses `black_box` to prevent the compiler from precomputing
repeated comparisons. Input and collator setup are outside the timer.

One run on macOS 26.6.2 arm64, using Apple Clang 21 and the pinned Rust nightly,
produced these results with ICU4X 2.3.1:

| Workload | Direct Rust, ns/pair | C++ through Crubit, ns/pair | Difference |
| --- | ---: | ---: | ---: |
| Short ASCII | 33.19 | 34.06 | +2.6% |
| English names | 49.31 | 50.56 | +2.5% |
| German phonebook | 52.92 | 54.71 | +3.4% |
| Japanese names | 53.36 | 55.03 | +3.1% |
| Chinese names | 49.63 | 50.61 | +2.0% |

The measured difference was about 0.9–1.8 nanoseconds per comparison. This
supports a small additional cost for the generated binding in this workload.
The result includes differences in loop compilation and inlining; it is not a
measurement of the ABI alone or a guarantee about total application runtime.
The JSON report includes raw samples, compiler versions, and input checksums.
The [recorded binding results](benchmark-results-bindings.json) contain the
samples behind the table above.

## Additional comparisons

ICU4C and ICU4X use different implementations and data representations, so a
comparison between them also measures those choices. The ICU4X team describes
its design goals and tradeoffs in
[Announcing ICU4X 1.0](https://blog.unicode.org/2022/09/announcing-icu4x-10.html).
To measure the complete sorting paths in this demo, run:

```sh
python3 benchmark/benchmark.py --json benchmark/benchmark-results.json
python3 benchmark/benchmark.py --dataset japanese --json benchmark/benchmark-results-japanese.json
python3 benchmark/benchmark.py --dataset chinese --json benchmark/benchmark-results-chinese.json
```

The runner creates a reproducible list of 10,000 synthetic contact names and
checks that both backends produce the same ordering. It then alternates between
the two executables and reports median sort times. Each process creates one
collator, warms it up, and sorts the original list 20 times. Input, copying the
unsorted list, and output are outside the timed region. The JSON report includes
collator setup times, raw samples, compiler versions, and the input checksum.
Use `--words`, `--iterations`, `--samples`, or repeated `--locale` options to
change the workload.

Recorded sort results are available for [Latin](benchmark-results-latin.json),
[Japanese](benchmark-results-japanese.json), and
[Chinese](benchmark-results-chinese.json) names.

To compare memory use on macOS or Linux, use the same Release build:

```sh
python3 benchmark/benchmark_memory.py --json benchmark/benchmark-results-memory.json
```

This runs each ordinary CLI in a separate process and uses `wait4` to record its
peak resident set size (RSS). It reports the median of seven runs for process
startup (`--version`), collator setup with no contacts, and sorting 10,000 or
100,000 names. Both programs receive identical input and must produce identical
output. The Python runner's memory is excluded. Use repeated `--words` and
`--locale` options, or `--dataset`, to select other workloads.

RSS includes resident executable and library pages, locale data, stacks, input
storage, and sorting allocations. It is a measure of the complete demo process,
not the Rust binding's allocation count or the installed size of either library.
The JSON report preserves raw byte counts, platform and compiler details, and
input checksums. Compare results on the same machine; operating systems account
for shared and file-backed pages differently.

Recorded memory results are available for
[Latin](benchmark-results-memory.json),
[Japanese](benchmark-results-memory-japanese.json), and
[Chinese](benchmark-results-memory-chinese.json) names.
