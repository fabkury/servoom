/* zlib (RFC 1950) / DEFLATE (RFC 1951) decompression, self-contained. Used by the 0x1D
 * layer-file container, whose payload is a zlib stream. */
#ifndef SERVOOM_CODEC_INFLATE_H
#define SERVOOM_CODEC_INFLATE_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

/* Inflate one zlib stream (2-byte header, deflate data, Adler-32 trailer) held in `in`.
 * Mirrors Python's zlib.decompress(): the stream must be complete and well formed, the
 * checksum must match, and bytes after the trailer are ignored. `expected_out` (0 =
 * unknown) only sizes the initial buffer. *out is malloc'd; caller frees. A stream that
 * inflates past `max_out` (0 = unlimited) fails with SERVOOM_ERR_CODEC. */
servoom_status sv_zlib_inflate(const uint8_t *in, size_t in_len, size_t expected_out,
                               size_t max_out, uint8_t **out, size_t *out_len);

#endif
