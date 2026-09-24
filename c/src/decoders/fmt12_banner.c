/* Format 12 (0x0C): 16x16 scrolling banner. Python BannerDecoder.
 *
 * File: [0x0C][mode][speed BE16][AES-CBC ciphertext of four raw 16x16 RGB tiles]. The
 * tiles side by side are one 64x16 strip that a 16x16 device scrolls (gallery FileType
 * 8). Decoded as that marquee: 64 frames of a 16x16 window sliding right-to-left over
 * the strip one pixel per frame, wrapping around, each lasting `speed` ms. The mode byte
 * (1..3 observed, meaning unknown) is ignored. servoom_pixel_bean_banner_strip()
 * recovers the flat strip. */
#include "decoders/decoders.h"

#include <stdlib.h>
#include <string.h>
#include "codec/aes_cbc.h"
#include "util/bytes.h"

#define BANNER_TILES 4
#define TILE_BYTES (16 * 16 * 3)

servoom_status sv_decode_fmt12(const uint8_t *data, size_t len, servoom_pixel_bean **out)
{
    *out = NULL;
    if (len < 3)
        return SERVOOM_ERR_CORRUPT;
    int speed = sv_be16(data + 1);
    const uint8_t *body = data + 3;
    size_t blen = len - 3;
    size_t usable = blen - (blen % 16);
    if (usable < BANNER_TILES * TILE_BYTES)
        return SERVOOM_ERR_CORRUPT;
    uint8_t *enc = sv_memdup(body, usable);
    if (!enc)
        return SERVOOM_ERR_NOMEM;
    servoom_status st = sv_aes_divoom_decrypt(enc, usable);
    if (st != SERVOOM_OK) {
        free(enc);
        return st;
    }
    /* strip: 16 rows x 64 columns, RGB */
    uint8_t strip[16 * 64 * 3];
    uint8_t tile[TILE_BYTES];
    for (int t = 0; t < BANNER_TILES; t++) {
        st = sv_compact_frame(enc + (size_t)t * TILE_BYTES, TILE_BYTES, 1, 1, tile);
        if (st != SERVOOM_OK) {
            free(enc);
            return st;
        }
        for (int y = 0; y < 16; y++)
            memcpy(strip + ((size_t)y * 64 + (size_t)t * 16) * 3, tile + (size_t)y * 16 * 3, 16 * 3);
    }
    free(enc);
    const int width = 64;
    servoom_pixel_bean *bean = sv_bean_new(12, width, speed, 1, 1);
    if (!bean)
        return SERVOOM_ERR_NOMEM;
    for (int f = 0; f < width; f++) {
        uint8_t *dst = bean->frames + (size_t)f * TILE_BYTES;
        for (int y = 0; y < 16; y++)
            for (int x = 0; x < 16; x++)
                memcpy(dst + ((size_t)y * 16 + x) * 3, strip + ((size_t)y * 64 + ((f + x) % 64)) * 3, 3);
    }
    *out = bean;
    return SERVOOM_OK;
}

servoom_status servoom_pixel_bean_banner_strip(const servoom_pixel_bean *bean, uint8_t *out)
{
    if (!bean || bean->format != 12 || bean->width != 16 || bean->height != 16 || bean->total_frames != 64)
        return SERVOOM_ERR_UNSUPPORTED;
    /* column x of the strip is column 0 of frame x */
    for (int x = 0; x < 64; x++) {
        const uint8_t *frame = bean->frames + (size_t)x * TILE_BYTES;
        for (int y = 0; y < 16; y++)
            memcpy(out + ((size_t)y * 64 + x) * 3, frame + (size_t)y * 16 * 3, 3);
    }
    return SERVOOM_OK;
}
