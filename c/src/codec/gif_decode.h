/* GIF reader that reproduces Pillow's frame semantics.
 *
 * Format 43 files may wrap an animated GIF, and the Python decoder feeds it through
 * Pillow's GifImagePlugin (LOADING_STRATEGY = RGB_AFTER_FIRST) and composites the frames
 * it yields. To stay bit-exact, this reader mirrors that plugin's observable behaviour:
 *
 *  - frame 0 is a palette image: canvas filled with the transparent index (or 0), the
 *    frame rect decoded into it, alpha 0 wherever the index equals the transparent index;
 *  - later frames are drawn onto a persistent RGB/RGBA canvas: the previous frame's
 *    disposal is applied first (2 = fill its rect with the transparent colour, or the
 *    background colour when the frame has no transparency; 3 = restore the rect from
 *    before that frame), then the new rect is pasted with the transparent index masked out;
 *  - the disposal method is sticky: an "unspecified" (0) graphic-control disposal keeps the
 *    previous frame's method;
 *  - a local palette that is the identity grey ramp counts as "no palette" (Pillow's mode L).
 *
 * Each yielded frame is the whole canvas as RGBA (alpha 0 = transparent), which is exactly
 * what `frame.convert("RGBA")` gives the Python compositor. */
#ifndef SERVOOM_CODEC_GIF_DECODE_H
#define SERVOOM_CODEC_GIF_DECODE_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

typedef struct sv_gif_anim {
    int width, height;   /* canvas size (may grow if a frame rect exceeds the header size) */
    int num_frames;
    uint8_t **frames;    /* num_frames pointers, each width*height*4 RGBA */
} sv_gif_anim;

servoom_status sv_gif_decode(const uint8_t *data, size_t len, sv_gif_anim *out);
void sv_gif_anim_free(sv_gif_anim *anim);

#endif
