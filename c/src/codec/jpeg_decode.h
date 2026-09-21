/* JPEG -> RGB via libjpeg-turbo, configured exactly like Pillow (ISLOW IDCT, fancy
 * upsampling, JCS_RGB output) so both decoders produce identical pixels. */
#ifndef SERVOOM_CODEC_JPEG_DECODE_H
#define SERVOOM_CODEC_JPEG_DECODE_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

/* Decode a JPEG in memory to a malloc'd width*height*3 RGB buffer. */
servoom_status sv_jpeg_decode_rgb(const uint8_t *data, size_t len, uint8_t **out_rgb,
                                  int *out_width, int *out_height);

#endif
