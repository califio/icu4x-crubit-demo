# Manual FFI comparison

This benchmark compares two complete ways for C++ to use the Rust `Collator`
adapter in [`rust/lib.rs`](../rust/lib.rs):

- **Manual FFI:** handwritten C functions create an opaque handle, compare
  strings, and destroy the handle. A C++ RAII owner handles cleanup and reports
  constructor errors.
- **Crubit:** generated bindings expose the Rust type and its methods. A small
  C++ facade gives the benchmark the same interface and constructor errors.

Both paths call the same compiled Rust adapter and ICU4X implementation. The
manual bridge links against the Rust artifacts already used by Crubit; it does
not compile a second copy of ICU4X. This isolates the choice of binding from
differences between ICU4C and ICU4X.

After completing the repository's [setup instructions](../README.md), run:

```sh
cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release -DENABLE_ASAN=OFF \
  -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
python3 benchmark/benchmark_manual_ffi.py --json benchmark/benchmark-results-manual-ffi.json
```

The runner builds `ffi-bench` and the ICU4X demo, runs ownership and error tests,
and then checks that both bindings return the same ordering for every input
pair. Each sample runs both paths in one process; their execution order
alternates. The reported numbers are medians of nine paired samples.

The comparison measurement reuses one collator for 10,000 word pairs repeated
100 times. Input, construction, warmup, validation, and output are outside that
timer. A second timer measures 1,000 complete create/use/destroy cycles. Each
cycle performs one comparison so the constructed object is actually used. Both
paths use the same C++ timing loops, and the runner checks their checksums.

## Recorded results

On macOS 26.6.2 arm64, with Apple Clang 21, the pinned Rust nightly, and ICU4X
2.3.1:

| Workload | Manual FFI, ns/pair | Crubit, ns/pair | Difference |
| --- | ---: | ---: | ---: |
| Short ASCII | 33.37 | 33.66 | +0.9% |
| English names | 49.53 | 49.71 | +0.4% |
| German phonebook | 54.74 | 55.16 | +0.8% |
| Japanese names | 54.46 | 55.19 | +1.3% |
| Chinese names | 51.40 | 52.20 | +1.5% |

Crubit added about 0.2–0.8 nanoseconds per comparison in this run. These small
differences include the C++ access paths and normal measurement noise. They
support similar steady-state performance for these two bindings, rather than
a general claim that every Crubit call has this cost. The Rust adapter is shared
by both paths, so this benchmark does not isolate its own overhead.

| Workload | Manual FFI, ns/cycle | Crubit, ns/cycle | Difference |
| --- | ---: | ---: | ---: |
| Short ASCII | 452.79 | 433.21 | −4.3% |
| English names | 466.42 | 432.38 | −7.3% |
| German phonebook | 227.00 | 203.88 | −10.2% |
| Japanese names | 169.08 | 152.62 | −9.7% |
| Chinese names | 475.50 | 444.21 | −6.6% |

The manual implementation allocates a `Box` for its opaque handle. Crubit lets
C++ hold the generated Rust type by value. That difference is a plausible
contributor to Crubit's lower lifecycle times; this test does not isolate the
allocator's cost. A more elaborate manual ABI could use caller-provided storage,
but would need its own size, alignment, and lifetime contract.

## Code to maintain

Using the runner's count of nonblank lines excluding full-line comments:

| Handwritten integration | Lines |
| --- | ---: |
| Manual Rust C ABI, C header, and C++ owner | 91 |
| Crubit include header and matching C++ facade | 30 |
| Rust adapter and error type shared by both | 32 |

The manual count includes construction, destruction, error handling, ownership,
and string conversion. The Crubit count includes the small facade used to make
the two benchmark interfaces equivalent. Generated output, build files, and the
shared timing code are excluded. The counts describe this example's maintenance
burden; they do not measure defect rates or Crubit's build-time cost.

The [raw results](benchmark-results-manual-ffi.json) contain every sample,
compiler versions, input hashes, an adapter-artifact hash, and per-file line
counts. See the [runner](benchmark_manual_ffi.py), [shared C++ loop](ffi_bench.cc),
[manual Rust ABI](../manual/manual_ffi.rs), [manual C++ owner](../manual/manual_collator.h), and
[Crubit facade](crubit_collator.h). The ICU4X developers discuss broader library
tradeoffs in [Announcing ICU4X 1.0](https://blog.unicode.org/2022/09/announcing-icu4x-10.html).
