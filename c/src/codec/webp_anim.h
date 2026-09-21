/* Animated/still WebP -> RGBA frames via libwebp's WebPAnimDecoder (what Pillow uses). */
#ifndef SERVOOM_CODEC_WEBP_ANIM_H
#define SERVOOM_CODEC_WEBP_ANIM_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

typedef struct sv_webp_anim {
    int width, height;
    int num_frames;
    uint8_t *rgba; /* num_frames * width * height * 4, each frame fully composited on the canvas */
} sv_webp_anim;

servoom_status sv_webp_decode_anim(const uint8_t *data, size_t len, sv_webp_anim *out);
void sv_webp_anim_free(sv_webp_anim *anim);

/* Decode a still (or first frame of a) WebP straight to RGB (alpha dropped). */
servoom_status sv_webp_decode_rgb(const uint8_t *data, size_t len, uint8_t **out_rgb,
                                  int *out_width, int *out_height);

#endif
