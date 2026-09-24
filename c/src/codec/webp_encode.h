/* RGB frames -> animated lossless WebP via libwebp's WebPAnimEncoder (what Pillow uses).
 *
 * Only compiled when SERVOOM_WITH_WEBP_ENCODER is on; the public wrappers in
 * servoom/pixel_bean.h report SERVOOM_ERR_UNSUPPORTED otherwise. */
#ifndef SERVOOM_CODEC_WEBP_ENCODE_H
#define SERVOOM_CODEC_WEBP_ENCODE_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

/* Encode `num_frames` row-major RGB frames of width*height*3 bytes (frame-major) as an
 * animated lossless WebP, every frame lasting `duration_ms`. On success *out is a malloc'd
 * buffer of *out_len bytes the caller frees with free().
 *
 * The encoder settings mirror Pillow's `Image.save(..., format="WEBP", save_all=True,
 * lossless=True)` defaults (quality 80, method 0, kmin 9, kmax 17, loop forever). Pixels are
 * exact; note that libwebp merges runs of identical consecutive frames into one longer
 * frame, so the frame *count* of the result can be lower than `num_frames`. */
servoom_status sv_webp_encode_anim(const uint8_t *rgb, int width, int height, int num_frames,
                                   int duration_ms, uint8_t **out, size_t *out_len);

#endif
