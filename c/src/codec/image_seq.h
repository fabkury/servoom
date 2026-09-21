/* Pillow-equivalent helpers for embedded image payloads:
 *  - composite an RGBA frame sequence over white, frame by frame (the Python
 *    `_composite_image_sequence`), producing RGB frames at the expected canvas size;
 *  - nearest-neighbour resize exactly as Image.resize(..., NEAREST). */
#ifndef SERVOOM_CODEC_IMAGE_SEQ_H
#define SERVOOM_CODEC_IMAGE_SEQ_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

/* Nearest resize of an RGB buffer (in place semantics: returns a new malloc'd buffer). */
uint8_t *sv_resize_nearest_rgb(const uint8_t *src, int sw, int sh, int dw, int dh);

/* Composite `n` RGBA frames (each w*h*4) over white, accumulating like Pillow's
 * base.paste(previous); base.paste(frame, mask=frame). Output: n RGB frames of
 * exp_w*exp_h*3 (resized with NEAREST when (w,h) != (exp_w,exp_h)), contiguous. */
servoom_status sv_composite_rgba_sequence(uint8_t *const *frames, int n, int w, int h,
                                          int exp_w, int exp_h, uint8_t **out_rgb);

/* Same, for frames stored contiguously (frame i at rgba + i*w*h*4). */
servoom_status sv_composite_rgba_contig(const uint8_t *rgba, int n, int w, int h,
                                        int exp_w, int exp_h, uint8_t **out_rgb);

#endif
