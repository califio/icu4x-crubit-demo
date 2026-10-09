add_executable(ffi-bench EXCLUDE_FROM_ALL ffi_bench.cc)
target_compile_options(ffi-bench PRIVATE -Wno-nontrivial-memcall)
target_link_libraries(ffi-bench PRIVATE manual_ffi collation)
