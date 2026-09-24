/* Internal: per-format decoders and the helpers they share.
 *
 * Every decoder receives the file contents AFTER the format byte (`data`, `len`) and
 * either fills *out with a new bean or returns an error, in which case *out is NULL. The
 * Python decoders are the specification: each function mirrors one class in
 * python/servoom/pixel_bean_decoder.py, including its error behaviour (where Python
 * raises or returns None, we return an error; where it silently pads, duplicates or
 * truncates frames, so do we). */
#ifndef SERVOOM_DECODERS_H
#define SERVOOM_DECODERS_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/pixel_bean.h"

/* --- shared helpers (common.c) ------------------------------------------- */

/* Allocate a bean with `total_frames` zeroed frames of (column_count*16) x (row_count*16). */
servoom_pixel_bean *sv_bean_new(int format, int total_frames, int speed, int row_count,
                                int column_count);

/* Python BaseDecoder._compact for ONE frame: interpret `frame_data` as 16x16 tiles (256
 * RGB pixels each, row-major inside the tile) laid out in the quirky tile order the Python
 * code uses (the tile column index wraps at row_count, not column_count) and write the
 * (H, W, 3) image into `out`. Errors: fewer than width*height*3 bytes (struct.error) or a
 * tile landing outside the canvas (numpy IndexError) -> SERVOOM_ERR_CORRUPT. */
servoom_status sv_compact_frame(const uint8_t *frame_data, size_t len, int row_count,
                                int column_count, uint8_t *out);

/* Python _frames_from_rgb for one frame: copy min(len, frame_size) bytes, zero the rest. */
void sv_frame_from_rgb(const uint8_t *buf, size_t len, size_t frame_size, uint8_t *out);

/* Python _decode_0x0c_frame: quantized-palette frame -> num_pixels*3 RGB bytes. Returns
 * SERVOOM_ERR_CODEC where Python raises. */
servoom_status sv_decode_0x0c_frame(const uint8_t *data, size_t len, int num_pixels,
                                    uint8_t *out_rgb);

/* --- per-format decoders ------------------------------------------------- */
servoom_status sv_decode_fmt08(const uint8_t *data, size_t len, servoom_pixel_bean **out);
servoom_status sv_decode_fmt09(const uint8_t *data, size_t len, servoom_pixel_bean **out);
servoom_status sv_decode_fmt17(const uint8_t *data, size_t len, servoom_pixel_bean **out);
servoom_status sv_decode_fmt18(const uint8_t *data, size_t len, servoom_pixel_bean **out);
servoom_status sv_decode_fmt26(const uint8_t *data, size_t len, servoom_pixel_bean **out);
servoom_status sv_decode_fmt31(const uint8_t *data, size_t len, servoom_pixel_bean **out);
servoom_status sv_decode_fmt41(const uint8_t *data, size_t len, servoom_pixel_bean **out);
servoom_status sv_decode_fmt42(const uint8_t *data, size_t len, servoom_pixel_bean **out);
servoom_status sv_decode_fmt43(const uint8_t *data, size_t len, servoom_pixel_bean **out);

/* Format 26 internals (fmt26_anim_multi64.c / fmt26_hier.c). `hdr` is the 5-byte header. */
servoom_status sv_decode_fmt26_multi64(const uint8_t *hdr, const uint8_t *body, size_t body_len,
                                       servoom_pixel_bean **out);
servoom_status sv_decode_fmt26_hier(const uint8_t *hdr, const uint8_t *body, size_t body_len,
                                    servoom_pixel_bean **out);

#endif
