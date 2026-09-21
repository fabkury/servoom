/* Format 43 (0x2B): embedded GIF / WebP container. Python AnimEmbeddedImageDecoder.
 *
 * The payload is located by magic (b'GIF8', else the first b'RIFF' if followed by 'WEBP'),
 * decoded with Pillow semantics and composited frame by frame over white. */
#include "decoders/decoders.h"

#include <stdlib.h>
#include <string.h>
#include "codec/gif_decode.h"
#include "codec/image_seq.h"
#include "codec/webp_anim.h"
#include "util/bytes.h"

servoom_status sv_decode_fmt43(const uint8_t *data, size_t len, servoom_pixel_bean **out)
{
    *out = NULL;
    if (len < 5)
        return SERVOOM_ERR_CORRUPT;
    int total_declared = data[0];
    (void)total_declared; /* Python ignores it: frame count comes from the image */
    int speed = sv_be16(data + 1);
    int row_count = data[3], column_count = data[4];
    int width = column_count * 16, height = row_count * 16;
    const uint8_t *rest = data + 5;
    size_t rest_len = len - 5;

    const uint8_t *payload = rest;
    size_t payload_len = rest_len;
    int kind = 0; /* 1 gif, 2 webp, 0 sniff */
    long off = sv_find(rest, rest_len, (const uint8_t *)"GIF8", 4, 0);
    if (off >= 0) {
        payload = rest + off;
        payload_len = rest_len - (size_t)off;
        kind = 1;
    } else {
        off = sv_find(rest, rest_len, (const uint8_t *)"RIFF", 4, 0);
        if (off >= 0 && (size_t)off + 12 <= rest_len && memcmp(rest + off + 8, "WEBP", 4) == 0) {
            payload = rest + off;
            payload_len = rest_len - (size_t)off;
            kind = 2;
        }
    }
    if (kind == 0) {
        /* Pillow sniffs the whole payload. Only GIF/WebP could plausibly succeed. */
        if (payload_len >= 6 && memcmp(payload, "GIF8", 4) == 0)
            kind = 1;
        else if (payload_len >= 12 && memcmp(payload, "RIFF", 4) == 0 &&
                 memcmp(payload + 8, "WEBP", 4) == 0)
            kind = 2;
        else
            return SERVOOM_ERR_CODEC; /* UnidentifiedImageError */
    }
    if (width <= 0 || height <= 0)
        return SERVOOM_ERR_CORRUPT;

    uint8_t *rgb = NULL;
    int n = 0;
    servoom_status st;
    if (kind == 1) {
        sv_gif_anim gif;
        st = sv_gif_decode(payload, payload_len, &gif);
        if (st != SERVOOM_OK)
            return st;
        st = sv_composite_rgba_sequence(gif.frames, gif.num_frames, gif.width, gif.height,
                                        width, height, &rgb);
        n = gif.num_frames;
        sv_gif_anim_free(&gif);
    } else {
        sv_webp_anim webp;
        st = sv_webp_decode_anim(payload, payload_len, &webp);
        if (st != SERVOOM_OK)
            return st;
        st = sv_composite_rgba_contig(webp.rgba, webp.num_frames, webp.width, webp.height,
                                      width, height, &rgb);
        n = webp.num_frames;
        sv_webp_anim_free(&webp);
    }
    if (st != SERVOOM_OK)
        return st;
    servoom_pixel_bean *bean = sv_bean_new(43, n, speed, row_count, column_count);
    if (!bean) {
        free(rgb);
        return SERVOOM_ERR_NOMEM;
    }
    memcpy(bean->frames, rgb, (size_t)n * width * height * 3);
    free(rgb);
    *out = bean;
    return SERVOOM_OK;
}
