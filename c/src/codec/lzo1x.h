/* LZO1X decompressor (in-house, no dependency on the GPL minilzo).
 *
 * Divoom formats 17 and 18 compress frames with LZO1X. The Python library uses lzallright,
 * whose "output size" argument is only a hint: the decompressor returns however many bytes
 * the stream actually encodes. This implementation does the same: the output buffer grows as
 * needed and the real size is returned. */
#ifndef SERVOOM_CODEC_LZO1X_H
#define SERVOOM_CODEC_LZO1X_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

/* Decompress `in_len` bytes. On success *out is malloc'd (`*out_len` bytes; caller frees).
 * `size_hint` pre-sizes the buffer (0 = unknown). Returns SERVOOM_ERR_CODEC on a malformed
 * stream (input overrun, bad look-behind, missing end marker). */
servoom_status sv_lzo1x_decompress(const uint8_t *in, size_t in_len, size_t size_hint,
                                   uint8_t **out, size_t *out_len);

#endif
