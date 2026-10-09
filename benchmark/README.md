# Binding benchmark

This benchmark compares two ways of calling the same Rust adapter in
[`rust/lib.rs`](../rust/lib.rs):

- **Rust adapter:** a Rust program calls `Collator::compare_utf8()` directly.
- **C++ through Crubit:** the C++ demo calls the same method through the
  generated binding.

Both paths ultimately call ICU4X's `CollatorBorrowed::compare_utf8()`. The Rust
baseline includes our adapter; it does not bypass it.

Run these commands from the repository root:

```sh
cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release -DENABLE_ASAN=OFF \
  -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
cmake --build build-release --parallel 8
python3 benchmark/benchmark_bindings.py --json benchmark/benchmark-results-bindings.json
```

The runner builds the Rust control with the pinned compiler and locked
dependencies. Each path reuses one collator and compares the same 10,000 word
pairs 100 times per sample. The runner alternates execution order, checks
matching results, and reports the median of nine samples. Input and collator
construction are outside the timer. `black_box` prevents the Rust compiler from
precomputing repeated comparisons.

On macOS 26.6.2 arm64, with Apple Clang 21, the pinned Rust nightly, and ICU4X
2.3.1, the recorded results were:

| Workload | Rust adapter, ns/pair | C++ through Crubit, ns/pair | Difference |
| --- | ---: | ---: | ---: |
| Short ASCII | 32.58 | 33.18 | +1.8% |
| English names | 48.62 | 49.10 | +1.0% |
| German phonebook | 53.10 | 54.36 | +2.4% |
| Japanese names | 53.73 | 54.54 | +1.5% |
| Chinese names | 49.54 | 50.63 | +2.2% |

The C++ path took about 1.0–2.4% longer, adding roughly
0.5–1.3 nanoseconds per comparison. This supports a small
cost for calling our Rust adapter through Crubit in this workload. The result
includes differences in loop compilation and inlining; it does not separately
measure the adapter's own cost or total application runtime.

The [raw results](benchmark-results-bindings.json) include compiler versions,
input checksums, and every sample. See the [runner](benchmark_bindings.py),
[Rust loop](compare_pairs.rs), and [C++ loop](benchmark.h) for the implementation.
The ICU4X developers discuss broader library-design tradeoffs in
[Announcing ICU4X 1.0](https://blog.unicode.org/2022/09/announcing-icu4x-10.html).
