find_package(Python3 REQUIRED COMPONENTS Interpreter)
set(manual_archive "${CMAKE_CURRENT_BINARY_DIR}/${CMAKE_STATIC_LIBRARY_PREFIX}manual_ffi${CMAKE_STATIC_LIBRARY_SUFFIX}")
add_custom_command(OUTPUT "${manual_archive}"
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/build_manual_ffi.py"
    --build-dir "${PROJECT_BINARY_DIR}" --toolchain "${Rust_TOOLCHAIN}"
    --output "${manual_archive}"
  DEPENDS cargo-build_locale_collator manual_ffi.rs build_manual_ffi.py
    "${PROJECT_BINARY_DIR}/${CMAKE_STATIC_LIBRARY_PREFIX}locale_collator${CMAKE_STATIC_LIBRARY_SUFFIX}"
    "${PROJECT_SOURCE_DIR}/rust/lib.rs" "${PROJECT_SOURCE_DIR}/rust/Cargo.toml"
    "${PROJECT_SOURCE_DIR}/rust/Cargo.lock"
  VERBATIM)
add_custom_target(manual_ffi_build DEPENDS "${manual_archive}")
add_library(manual_ffi STATIC IMPORTED GLOBAL)
set_target_properties(manual_ffi PROPERTIES IMPORTED_LOCATION "${manual_archive}")
add_dependencies(manual_ffi manual_ffi_build)
target_include_directories(manual_ffi INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}")
