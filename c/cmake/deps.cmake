# Third-party dependencies for the C library.
#
# Small, single-file libraries are vendored under third_party/ (tiny-AES-c, cJSON).
# The big codecs are fetched at configure time with FetchContent, pinned to release
# tarballs, and built as static libraries inside the build tree (never installed
# system-wide, never committed).
#
#   zstd          - layer-file streams and artwork format 42
#   libwebp       - animated/lossless WebP payloads (format 43, layer format 0x28)
#   libjpeg-turbo - JPEG frames (formats 31 and 41); same decoder Pillow uses, so the
#                   Python oracle and the C port agree bit for bit
#   curl          - HTTPS transport for the Divoom cloud client (optional, SERVOOM_WITH_CLIENT)

include(FetchContent)
set(FETCHCONTENT_QUIET OFF)

# ---- zstd ---------------------------------------------------------------------
set(ZSTD_BUILD_PROGRAMS OFF CACHE BOOL "" FORCE)
set(ZSTD_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(ZSTD_BUILD_CONTRIB OFF CACHE BOOL "" FORCE)
set(ZSTD_BUILD_SHARED OFF CACHE BOOL "" FORCE)
set(ZSTD_BUILD_STATIC ON CACHE BOOL "" FORCE)
set(ZSTD_LEGACY_SUPPORT OFF CACHE BOOL "" FORCE)
set(ZSTD_MULTITHREAD_SUPPORT OFF CACHE BOOL "" FORCE)
FetchContent_Declare(zstd
  URL https://github.com/facebook/zstd/releases/download/v1.5.7/zstd-1.5.7.tar.gz
  URL_HASH SHA256=eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3
  SOURCE_SUBDIR build/cmake
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE)

# ---- libwebp ------------------------------------------------------------------
set(WEBP_BUILD_ANIM_UTILS OFF CACHE BOOL "" FORCE)
set(WEBP_BUILD_CWEBP OFF CACHE BOOL "" FORCE)
set(WEBP_BUILD_DWEBP OFF CACHE BOOL "" FORCE)
set(WEBP_BUILD_GIF2WEBP OFF CACHE BOOL "" FORCE)
set(WEBP_BUILD_IMG2WEBP OFF CACHE BOOL "" FORCE)
set(WEBP_BUILD_VWEBP OFF CACHE BOOL "" FORCE)
set(WEBP_BUILD_WEBPINFO OFF CACHE BOOL "" FORCE)
set(WEBP_BUILD_WEBPMUX OFF CACHE BOOL "" FORCE)
set(WEBP_BUILD_EXTRAS OFF CACHE BOOL "" FORCE)
set(WEBP_BUILD_LIBWEBPMUX ON CACHE BOOL "" FORCE)
set(WEBP_LINK_STATIC ON CACHE BOOL "" FORCE)
set(WEBP_ENABLE_SIMD ON CACHE BOOL "" FORCE)
FetchContent_Declare(libwebp
  URL https://github.com/webmproject/libwebp/archive/refs/tags/v1.6.0.tar.gz
  URL_HASH SHA256=93a852c2b3efafee3723efd4636de855b46f9fe1efddd607e1f42f60fc8f2136
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE)

# ---- libjpeg-turbo ------------------------------------------------------------
# libjpeg-turbo refuses add_subdirectory(), so it is built and installed into the build
# tree as an external project and consumed as an imported static library.
include(ExternalProject)
set(_jpeg_install ${CMAKE_BINARY_DIR}/_deps/libjpeg-turbo-install)
if(MSVC)
  set(_jpeg_lib ${_jpeg_install}/lib/jpeg-static.lib)
else()
  set(_jpeg_lib ${_jpeg_install}/lib/libjpeg.a)
endif()
set(_jpeg_tls_args "")
if(CMAKE_TLS_CAINFO)
  set(_jpeg_tls_args TLS_CAINFO ${CMAKE_TLS_CAINFO})
endif()
ExternalProject_Add(libjpeg_turbo_ep
  URL https://github.com/libjpeg-turbo/libjpeg-turbo/archive/refs/tags/3.1.2.tar.gz
  URL_HASH SHA256=560f6338b547544c4f9721b18d8b87685d433ec78b3c644c70d77adad22c55e6
  ${_jpeg_tls_args}
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
  PREFIX ${CMAKE_BINARY_DIR}/_deps/libjpeg-turbo-ep
  INSTALL_DIR ${_jpeg_install}
  CMAKE_ARGS
    -DCMAKE_INSTALL_PREFIX=<INSTALL_DIR>
    -DCMAKE_INSTALL_LIBDIR=lib
    -DCMAKE_BUILD_TYPE=Release
    -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
    -DCMAKE_MAKE_PROGRAM=${CMAKE_MAKE_PROGRAM}
    -DENABLE_SHARED=OFF -DENABLE_STATIC=ON
    -DWITH_TURBOJPEG=OFF -DWITH_JAVA=OFF -DWITH_JPEG8=ON
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON
  BUILD_BYPRODUCTS ${_jpeg_lib})
file(MAKE_DIRECTORY ${_jpeg_install}/include)  # must exist at generate time
add_library(servoom_jpeg STATIC IMPORTED GLOBAL)
set_target_properties(servoom_jpeg PROPERTIES
  IMPORTED_LOCATION ${_jpeg_lib}
  INTERFACE_INCLUDE_DIRECTORIES ${_jpeg_install}/include)
add_dependencies(servoom_jpeg libjpeg_turbo_ep)

FetchContent_MakeAvailable(zstd libwebp)

# ---- curl (optional) ----------------------------------------------------------
if(SERVOOM_WITH_CLIENT)
  set(BUILD_CURL_EXE OFF CACHE BOOL "" FORCE)
  set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
  set(BUILD_STATIC_LIBS ON CACHE BOOL "" FORCE)
  set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
  set(BUILD_LIBCURL_DOCS OFF CACHE BOOL "" FORCE)
  set(BUILD_MISC_DOCS OFF CACHE BOOL "" FORCE)
  set(ENABLE_CURL_MANUAL OFF CACHE BOOL "" FORCE)
  set(BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
  set(HTTP_ONLY ON CACHE BOOL "" FORCE)
  set(CURL_USE_LIBPSL OFF CACHE BOOL "" FORCE)
  set(CURL_USE_LIBSSH2 OFF CACHE BOOL "" FORCE)
  set(USE_LIBIDN2 OFF CACHE BOOL "" FORCE)
  set(USE_NGHTTP2 OFF CACHE BOOL "" FORCE)
  set(CURL_ZLIB OFF CACHE BOOL "" FORCE)
  set(CURL_BROTLI OFF CACHE BOOL "" FORCE)
  set(CURL_ZSTD OFF CACHE BOOL "" FORCE)
  set(CURL_DISABLE_LDAP ON CACHE BOOL "" FORCE)
  set(CURL_ENABLE_EXPORT_TARGET OFF CACHE BOOL "" FORCE)
  if(WIN32)
    set(CURL_USE_SCHANNEL ON CACHE BOOL "" FORCE)   # native Windows TLS, no OpenSSL needed
    set(CURL_USE_OPENSSL OFF CACHE BOOL "" FORCE)
  elseif(APPLE)
    set(CURL_USE_SECTRANSP ON CACHE BOOL "" FORCE)
  else()
    set(CURL_USE_OPENSSL ON CACHE BOOL "" FORCE)    # needs libssl-dev on Linux
  endif()
  FetchContent_Declare(curl
    URL https://github.com/curl/curl/releases/download/curl-8_16_0/curl-8.16.0.tar.gz
    URL_HASH SHA256=a21e20476e39eca5a4fc5cfb00acf84bbc1f5d8443ec3853ad14c26b3c85b970
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
  FetchContent_MakeAvailable(curl)
endif()
