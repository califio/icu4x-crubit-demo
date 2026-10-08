include(ExternalProject)
find_program(ICU_MAKE_EXECUTABLE NAMES gmake make REQUIRED)
find_package(Threads REQUIRED)

if(NOT EXISTS "${ICU4C_SOURCE}/source/configure")
  message(FATAL_ERROR "Missing upstream ICU4C sources. Run python3 setup.py first.")
endif()
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/dependencies.json" dependency_pins)
string(JSON expected_locid_sha GET "${dependency_pins}" icu4c locid_sha256)
file(SHA256 "${ICU4C_SOURCE}/source/common/locid.cpp" actual_locid_sha)
if(NOT actual_locid_sha STREQUAL expected_locid_sha)
  message(FATAL_ERROR "The ICU4C source does not match the unmodified 66.1 release")
endif()

set(icu_install "${CMAKE_CURRENT_BINARY_DIR}/icu4c-install")
set(icu_compile_flags "-O3 -DNDEBUG -fPIC")
set(icu_link_flags "")
if(ENABLE_ASAN)
  set(icu_compile_flags "-O1 -g -fPIC -fsanitize=address -fno-omit-frame-pointer")
  set(icu_link_flags "-fsanitize=address")
endif()
set(icu_env "CC=${CMAKE_C_COMPILER}" "CXX=${CMAKE_CXX_COMPILER}"
  "CFLAGS=${icu_compile_flags}" "CXXFLAGS=${icu_compile_flags} -std=c++11"
  "LDFLAGS=${icu_link_flags}" "ASAN_OPTIONS=detect_leaks=0")
set(icu_i18n "${icu_install}/lib/libicui18n.a")
set(icu_uc "${icu_install}/lib/libicuuc.a")
set(icu_data "${icu_install}/lib/libicudata.a")
file(MAKE_DIRECTORY "${icu_install}/include")

ExternalProject_Add(icu4c_upstream
  SOURCE_DIR "${ICU4C_SOURCE}/source"
  BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}/icu4c-build"
  INSTALL_DIR "${icu_install}"
  DOWNLOAD_COMMAND ""
  UPDATE_COMMAND ""
  CONFIGURE_COMMAND ${CMAKE_COMMAND} -E env ${icu_env}
    <SOURCE_DIR>/configure --prefix=<INSTALL_DIR> --libdir=<INSTALL_DIR>/lib
    --disable-shared --enable-static --with-data-packaging=static
    --disable-tests --disable-samples --disable-extras --disable-icuio
  BUILD_COMMAND ${CMAKE_COMMAND} -E env ${icu_env} ${ICU_MAKE_EXECUTABLE} -j8
  INSTALL_COMMAND ${CMAKE_COMMAND} -E env ${icu_env} ${ICU_MAKE_EXECUTABLE} install
  BUILD_BYPRODUCTS "${icu_i18n}" "${icu_uc}" "${icu_data}"
)

add_library(upstream_icu4c INTERFACE)
add_dependencies(upstream_icu4c icu4c_upstream)
target_compile_definitions(upstream_icu4c INTERFACE U_STATIC_IMPLEMENTATION)
target_include_directories(upstream_icu4c INTERFACE "${icu_install}/include")
target_link_libraries(upstream_icu4c INTERFACE "${icu_i18n}" "${icu_uc}" "${icu_data}" Threads::Threads ${CMAKE_DL_LIBS} m)
