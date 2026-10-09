# Memory-safe collation bindings

This example is a small contact-list application. The user chooses a locale,
and the app sorts names using that locale's alphabet and collation rules. For
example, German phonebook ordering treats an umlaut differently from ordinary
German dictionary ordering.

There are two C++ executables. `icu4c-demo` uses the unmodified upstream ICU4C
66.1 release. `icu4x-demo` calls ICU4X 2.3.1 through a Crubit-generated C++
binding. A long locale containing a collation keyword reaches CVE-2021-30535
during ICU4C collator construction. The same input completes through ICU4X.
The demonstrated impact is a use-after-free and process failure.

## Build

Install Python 3.9+, Git, CMake 3.22+, GNU Make, a recent Clang with C++20/ASan
support, and Rustup. Crubit's support libraries also use Abseil and Protobuf;
install their development packages or let CMake fetch them.

```sh
python3 setup.py
cmake -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
cmake --build build --parallel 8
python3 verify.py
```

The setup script downloads the official ICU4C source archive and checks its
SHA-256. It also fetches pinned Crubit and Corrosion revisions and installs the
matching Rust nightly. CMake builds ICU4C from its original configure script
with AddressSanitizer enabled. Dependency versions are in `dependencies.json`
and `rust/Cargo.lock`.

Tested on macOS arm64 with Apple Clang 21. Other platforms have not been tested.

## Run

With no names supplied, each program sorts a small built-in contact list:

```sh
./build/icu4c-demo
./build/icu4x-demo
```

Try your own contacts, then run the CVE comparison:

```sh
./build/icu4c-demo --locale 'de@collation=phonebook' Müller Mueller Meyer
./build/icu4x-demo --locale 'de@collation=phonebook' Müller Mueller Meyer

./build/icu4c-demo --cve
./build/icu4x-demo --cve
```

The first CVE command prints an ASan use-after-free report. The second prints
the sorted contact list. `--version` identifies the backend. To read contacts
from a file or pipe, use `--stdin`:

```sh
printf '%s\n' Zimmermann Müller Andersson | ./build/icu4x-demo --stdin
```

## Benchmark

The [benchmark guide](benchmark/README.md) compares the same Rust `Collator`
adapter called from Rust and from C++ through Crubit. It includes the measured
results and reproduction command. The complete [handwritten C FFI example](manual/README.md)
is in `manual/`. An optional [comparison with Crubit](benchmark/manual-ffi.md)
measures both interfaces. Benchmark files are under `benchmark/`.

## Code layout

The layout follows the [safe-bindings examples](https://github.com/google/safe-bindings):

```text
main.cc                 C++ application using the Rust-backed collator
collation.h             Public C++ binding header
contacts.cc/.h          CLI handling, locale compatibility, and example contacts
manual/                 Handwritten C FFI, Rust bridge, and C++ owner
benchmark/             Benchmark sources, runners, and documentation
rust/lib.rs             Small Rust API around ICU4X
rust/Cargo.toml          Rust crate definition
CMakeLists.txt          Binding generation and example targets
legacy/main.cc          Equivalent application using ICU4C
cmake/icu4c.cmake       Build of the historical upstream ICU4C release
```

`main.cc` includes `collation.h`, converts the selected locale to a BCP 47
identifier with `contacts::ToLanguageTag`, creates a collator, and calls its
generated `compare_utf8` method from `std::stable_sort`. The Rust binding passes
the identifier to ICU4X's locale parser and stores `CollatorBorrowed<'static>`
directly. Corrosion runs Crubit to generate the C++ declarations and Rust bridge
code. The generated header is under
`build/corrosion_generated/crubit/locale_collator/include/crubit/`.

The demo accepts BCP 47 locale identifiers and the legacy ICU `collation`
keyword. A production migration would need to define which locale options and
ordering differences it supports.

## References

- [ICU4C 66.1 release](https://github.com/unicode-org/icu/releases/tag/release-66-1)
- [CVE-2021-30535 upstream fix](https://github.com/unicode-org/icu/commit/2dc5bea9061b4fb05cd03e21b775dd944a0eb81d)
- [ICU4X collator API](https://docs.rs/icu_collator/2.3.1/icu_collator/struct.CollatorBorrowed.html)
- [Third-party notices](NOTICE.md)
