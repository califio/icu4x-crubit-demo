cmake_minimum_required(VERSION 3.22)
project(collation VERSION 0.1.0 LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(DEPS_DIR "${CMAKE_CURRENT_SOURCE_DIR}/third_party" CACHE PATH "Pinned dependencies")
set(ICU4C_SOURCE "${DEPS_DIR}/icu4c" CACHE PATH "Upstream ICU4C 66.1 source release")
set(CRUBIT_SOURCE "${DEPS_DIR}/crubit" CACHE PATH "Pinned Crubit source")
set(CORROSION_SOURCE "${DEPS_DIR}/corrosion" CACHE PATH "Pinned Corrosion source")
set(Rust_TOOLCHAIN nightly-2026-09-07 CACHE STRING "Pinned Rust compiler")
set(CORROSION_TOOLS_RUST_TOOLCHAIN "${Rust_TOOLCHAIN}" CACHE STRING "Rust tools compiler")
option(ENABLE_ASAN "Instrument the vulnerable ICU4C executable" ON)

if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  message(FATAL_ERROR "Crubit requires Clang. Configure with -DCMAKE_CXX_COMPILER=clang++")
endif()

# Same structure as a safe-bindings component: import the Rust crate, expose a
# small C++ header, and link the example's main.cc to the binding target.
set(installed_cargo_crubit "${CRUBIT_SOURCE}/target/release/cargo-cpp_api_from_rust" CACHE FILEPATH "Crubit Cargo driver" FORCE)
if(NOT EXISTS "${installed_cargo_crubit}")
  message(FATAL_ERROR "Missing Crubit Cargo driver. Run python3 setup.py first.")
endif()
include(FetchContent)
FetchContent_Declare(Crubit SOURCE_DIR "${CRUBIT_SOURCE}")
FetchContent_Declare(Corrosion SOURCE_DIR "${CORROSION_SOURCE}")
FetchContent_MakeAvailable(Corrosion)
corrosion_experimental_crubit(locale_collator)
corrosion_import_crate(MANIFEST_PATH rust/Cargo.toml LOCKED)
get_target_property(support_targets crubit_support INTERFACE_LINK_LIBRARIES)
add_dependencies(crubit_support ${support_targets})

add_library(collation INTERFACE)
target_include_directories(collation INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}")
target_link_libraries(collation INTERFACE locale_collator crubit_support)
add_dependencies(collation crubit_support)

add_executable(icu4x-demo main.cc contacts.cc)
target_compile_options(icu4x-demo PRIVATE -Wno-nontrivial-memcall)
target_link_libraries(icu4x-demo PRIVATE collation)

add_subdirectory(benchmark)

# Historical implementation used only by the comparison executable.
include(cmake/icu4c.cmake)
add_executable(icu4c-demo legacy/main.cc contacts.cc)
target_include_directories(icu4c-demo PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
target_link_libraries(icu4c-demo PRIVATE upstream_icu4c)
if(ENABLE_ASAN)
  target_compile_options(icu4c-demo PRIVATE -O1 -g -fsanitize=address -fno-omit-frame-pointer)
  target_link_options(icu4c-demo PRIVATE -fsanitize=address)
endif()
