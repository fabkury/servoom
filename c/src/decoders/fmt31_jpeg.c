/* Format 31 (0x1F): embedded JPEG animation. Python Decoder0x1F. */
#include "decoders/decoders.h"

#include <stdlib.h>
#include <string.h>
#include "codec/image_seq.h"
#include "codec/jpeg_decode.h"
#include "util/bytes.h"

servoom_status sv_decode_fmt31(const uint8_t *data, size_t len, servoom_pixel_bean **out)
{
    static const uint8_t SOI[2] = {0xFF, 0xD8}, EOI[2] = {0xFF, 0xD9};
    *out = NULL;
    if (len < 5)
        return SERVOOM_ERR_CORRUPT; /* Python returns None */
    int total_frames = data[0];
    int speed = sv_be16(data + 1);
    int row_count = data[3], column_count = data[4];
    int width = column_count * 16, height = row_count * 16;
    const uint8_t *payload = data + 5;
    size_t plen = len - 5;
    size_t frame_size = (size_t)width * height * 3;

    /* Collect decoded frames (at most total_frames). */
    servoom_pixel_bean *bean = sv_bean_new(31, total_frames, speed, row_count, column_count);
    if (!bean)
        return SERVOOM_ERR_NOMEM;
    int count = 0;
    size_t pos = 0;
    while (pos < plen && count < total_frames) {
        long soi = sv_find(payload, plen, SOI, 2, pos);
        if (soi < 0)
            break;
        long eoi = sv_find(payload, plen, EOI, 2, (size_t)soi + 2);
        if (eoi < 0)
            eoi = (long)plen - 2;
        size_t jlen = (size_t)(eoi + 2 - soi);
        uint8_t *rgb = NULL;
        int jw = 0, jh = 0;
        servoom_status st = sv_jpeg_decode_rgb(payload + soi, jlen, &rgb, &jw, &jh);
        if (st == SERVOOM_ERR_NOMEM) {
            servoom_pixel_bean_free(bean);
            return st;
        }
        if (st == SERVOOM_OK) {
            uint8_t *dst = bean->frames + (size_t)count * frame_size;
            if (jw == width && jh == height) {
                memcpy(dst, rgb, frame_size);
            } else if (width > 0 && height > 0) {
                uint8_t *r = sv_resize_nearest_rgb(rgb, jw, jh, width, height);
                if (!r) {
                    free(rgb);
                    servoom_pixel_bean_free(bean);
                    return SERVOOM_ERR_NOMEM;
                }
                memcpy(dst, r, frame_size);
                free(r);
            } else {
                free(rgb); /* Pillow: resize to a zero size raises -> frame skipped */
                pos = (size_t)eoi + 2;
                continue;
            }
            free(rgb);
            count++;
        }
        /* decode failure: warn and continue (frame skipped) */
        pos = (size_t)eoi + 2;
    }
    if (count == 0) {
        /* "no JPEG frames extracted, creating blank frames": total_frames black frames */
        memset(bean->frames, 0, frame_size * (size_t)total_frames);
        bean->total_frames = total_frames;
    } else {
        bean->total_frames = count;
    }
    *out = bean;
    return SERVOOM_OK;
}
