/* Decoded Divoom artwork ("pixel bean"): frames of 24-bit RGB plus header metadata.
 *
 * Mirrors servoom.pixel_bean.PixelBean / PixelBeanDecoder in the Python library. Every
 * artwork container format the Python decoders understand is supported:
 *
 *   9  (0x09) 16x16 animation, AES-CBC encrypted raw RGB
 *   17 (0x11) single picture, AES-CBC + LZO1X
 *   18 (0x12) 32x32 / 64x64 animation, AES-CBC + LZO1X per frame
 *   26 (0x1A) 64x64 / 128x128 animation, quantized-palette frames (0x0C) or the
 *             hierarchical palette scheme (0x11 / 0x13 / 0x15)
 *   31 (0x1F) 128x128 embedded JPEG animation
 *   41 (0x29) 256x256 JPEG sequence
 *   42 (0x2A) 256x256 zstd-compressed raw RGB frames
 *   43 (0x2B) 256x256 embedded GIF / WebP container
 *
 * Decoding is a faithful port: for every sample in the reference corpus the C output is
 * byte-for-byte identical to the Python decoder's, quirks included.
 */
#ifndef SERVOOM_PIXEL_BEAN_H
#define SERVOOM_PIXEL_BEAN_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct servoom_pixel_bean {
    int format;        /* container format byte (9, 17, 18, 26, 31, 41, 42, 43) */
    int total_frames;  /* number of decoded frames (may differ from the header's claim) */
    int speed;         /* frame delay in milliseconds */
    int row_count;     /* canvas height in 16-pixel tiles */
    int column_count;  /* canvas width in 16-pixel tiles */
    int width;         /* column_count * 16 */
    int height;        /* row_count * 16 */
    uint8_t *frames;   /* total_frames * width * height * 3 bytes, row-major RGB, frame-major */
} servoom_pixel_bean;

/* Decode a .dat file / an in-memory copy of one. On success *out is a new bean the caller
 * frees with servoom_pixel_bean_free(). On failure *out is NULL. */
servoom_status servoom_decode_file(const char *path, servoom_pixel_bean **out);
servoom_status servoom_decode_memory(const uint8_t *data, size_t len, servoom_pixel_bean **out);

/* Pointer to frame `index` (0-based), width*height*3 bytes; NULL if out of range. */
const uint8_t *servoom_pixel_bean_frame(const servoom_pixel_bean *bean, int index);

/* Size in bytes of one frame (width * height * 3). */
size_t servoom_pixel_bean_frame_size(const servoom_pixel_bean *bean);

void servoom_pixel_bean_free(servoom_pixel_bean *bean);

/* Whether `format_byte` is one of the artwork container formats above. */
int servoom_format_is_artwork(int format_byte);

/* Write frame `index` as a binary PPM (P6) file. Handy for eyeballing decoder output. */
servoom_status servoom_pixel_bean_write_ppm(const servoom_pixel_bean *bean, int index,
                                            const char *path);

#ifdef __cplusplus
}
#endif
#endif
