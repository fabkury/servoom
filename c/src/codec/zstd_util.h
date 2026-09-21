/* zstd helpers: streaming decompression into a growable buffer. */
#ifndef SERVOOM_CODEC_ZSTD_UTIL_H
#define SERVOOM_CODEC_ZSTD_UTIL_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

#define SV_ZSTD_MAGIC "\x28\xb5\x2f\xfd"

/* Decompress the first zstd frame in `in`.
 *
 * strict = 0 mirrors python-zstandard's decompressobj().decompress(): the frame need not
 *   declare its content size, a frame that ends before the input does leaves the trailing
 *   bytes unread, and a truncated frame yields what could be decoded.
 * strict = 1 mirrors ZstdDecompressor().decompress(): the frame header must declare the
 *   content size, the frame must be complete and must consume the whole input.
 *
 * *out is malloc'd; caller frees. `max_out` (0 = unlimited) guards against bombs. */
servoom_status sv_zstd_decompress(const uint8_t *in, size_t in_len, int strict, size_t max_out,
                                  uint8_t **out, size_t *out_len);

#endif
