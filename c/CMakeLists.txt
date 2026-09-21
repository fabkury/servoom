cmake_minimum_required(VERSION 3.24)
project(servoom C)

# servoom in C: decoders for every Divoom artwork/layer format plus a Divoom cloud client.
# See README.md in this directory. Build artifacts live in build/ (git-ignored).

option(SERVOOM_WITH_CLIENT "Build the Divoom cloud client (needs libcurl, fetched)" ON)
option(SERVOOM_BUILD_CLI "Build the servoom command-line tool" ON)
option(SERVOOM_BUILD_TESTS "Build the test programs" ON)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

include(cmake/deps.cmake)

# ---- third-party sources vendored into the tree --------------------------------
add_library(servoom_vendored STATIC
  third_party/tiny-AES-c/aes.c
  third_party/cJSON/cJSON.c)
target_include_directories(servoom_vendored PUBLIC third_party/tiny-AES-c third_party/cJSON)
target_compile_definitions(servoom_vendored PUBLIC CBC=1 ECB=0 CTR=0 AES128=1)

# ---- the library --------------------------------------------------------------
set(SERVOOM_SOURCES
  src/util/bytes.c
  src/util/sha256.c
  src/util/md5.c
  src/util/fs.c
  src/codec/lzo1x.c
  src/codec/aes_cbc.c
  src/codec/zstd_util.c
  src/codec/jpeg_decode.c
  src/codec/gif_decode.c
  src/codec/webp_anim.c
  src/codec/image_seq.c
  src/decoders/pixel_bean.c
  src/decoders/common.c
  src/decoders/fmt09_anim_single.c
  src/decoders/fmt17_pic_multi.c
  src/decoders/fmt18_anim_multi.c
  src/decoders/fmt26_anim_multi64.c
  src/decoders/fmt26_hier.c
  src/decoders/fmt31_jpeg.c
  src/decoders/fmt41_jpeg_seq.c
  src/decoders/fmt42_zstd_rgb.c
  src/decoders/fmt43_embedded.c
  src/layer/layer_file.c
  src/error.c)
if(SERVOOM_WITH_CLIENT)
  list(APPEND SERVOOM_SOURCES src/client/http.c src/client/client.c)
endif()

add_library(servoom STATIC ${SERVOOM_SOURCES})
target_include_directories(servoom PUBLIC include PRIVATE src)
target_link_libraries(servoom PUBLIC servoom_vendored PRIVATE libzstd_static webp webpdemux servoom_jpeg)
target_compile_definitions(servoom PRIVATE SERVOOM_WITH_CLIENT=$<BOOL:${SERVOOM_WITH_CLIENT}>)
target_include_directories(servoom PRIVATE ${zstd_SOURCE_DIR}/lib ${libwebp_SOURCE_DIR}/src ${libwebp_SOURCE_DIR})
if(SERVOOM_WITH_CLIENT)
  target_link_libraries(servoom PRIVATE CURL::libcurl)
  target_compile_definitions(servoom PRIVATE CURL_STATICLIB)
endif()
if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(servoom PRIVATE -Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wno-sign-conversion)
endif()

# ---- CLI ----------------------------------------------------------------------
if(SERVOOM_BUILD_CLI)
  add_executable(servoom-cli cli/main.c)
  set_target_properties(servoom-cli PROPERTIES OUTPUT_NAME servoom)
  target_link_libraries(servoom-cli PRIVATE servoom)
  target_include_directories(servoom-cli PRIVATE src)
endif()

# ---- tests --------------------------------------------------------------------
if(SERVOOM_BUILD_TESTS)
  enable_testing()
  foreach(t test_units test_corpus test_live)
    add_executable(${t} tests/${t}.c tests/testlib.c)
    target_link_libraries(${t} PRIVATE servoom PRIVATE libzstd_static webp webpdemux)
    target_include_directories(${t} PRIVATE src ${zstd_SOURCE_DIR}/lib ${libwebp_SOURCE_DIR}/src)
    target_compile_definitions(${t} PRIVATE SERVOOM_WITH_CLIENT=$<BOOL:${SERVOOM_WITH_CLIENT}>
      SERVOOM_REPO_ROOT="${CMAKE_CURRENT_SOURCE_DIR}/..")
    add_test(NAME ${t} COMMAND ${t})
    set_tests_properties(${t} PROPERTIES SKIP_RETURN_CODE 77)
  endforeach()
endif()
