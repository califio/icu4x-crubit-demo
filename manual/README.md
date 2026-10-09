# Handwritten C++/Rust interface

This example exposes the same [Rust `Collator` adapter](../rust/lib.rs) as the
Crubit-backed application through a handwritten C ABI.

- [`manual_ffi.h`](manual_ffi.h) declares the opaque handle and the create,
  compare, and destroy functions.
- [`manual_ffi.rs`](manual_ffi.rs) implements those functions in Rust.
- [`manual_collator.h`](manual_collator.h) provides a move-only C++ owner that
  releases the handle automatically.
- [`collator_error.h`](collator_error.h) carries constructor error codes into C++.

After completing the repository's [setup instructions](../README.md), build the
manual library from the repository root:

```sh
cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release -DENABLE_ASAN=OFF \
  -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
cmake --build build-release --target manual_ffi_build --parallel 8
```

The CMake target builds `build-release/manual/libmanual_ffi.a` against the same
compiled Rust artifacts used by Crubit. This lets the [optional benchmark](../benchmark/manual-ffi.md)
compare the two interfaces without compiling a different copy of ICU4X.
