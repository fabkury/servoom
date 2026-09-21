/* Format 41 (0x29): JPEG sequence at 256x256. Python Format41Decoder. */
#include "decoders/decoders.h"

#include <stdlib.h>
#include <string.h>
#include "codec/image_seq.h"
#include "codec/jpeg_decode.h"
#include "util/bytes.h"

#define RESERVED_HEADER_LEN 9

servoom_status sv_decode_fmt41(const uint8_t *data, size_t len, servoom_pixel_bean **out)
{
    static const uint8_t SOI[2] = {0xFF, 0xD8}, EOI[2] = {0xFF, 0xD9};
    static const uint8_t GAP[3] = {0x02, 0x00, 0x00};
    *out = NULL;
    if (len < 5)
        return SERVOOM_ERR_CORRUPT; /* header too short -> None */
    int total_frames = data[0];
    int speed = (data[1] << 8) | data[2];
    int row_count = data[3] ? data[3] : 1;
    int column_count = data[4] ? data[4] : 1;
    size_t pos = 5;
    /* reserved bytes: skipped, truncation only warns */
    pos += RESERVED_HEADER_LEN;
    if (pos > len)
        pos = len;
    const uint8_t *payload = data + pos;
    size_t plen = len - pos;
    if (plen == 0)
        return SERVOOM_ERR_CORRUPT; /* empty payload -> None */
    int width = column_count * 16, height = row_count * 16;
    size_t frame_size = (size_t)width * height * 3;

    /* _extract_jpeg_frames */
    size_t cap = 16, nj = 0;
    struct { size_t off, len; } *jpegs = malloc(cap * sizeof(*jpegs));
    if (!jpegs)
        return SERVOOM_ERR_NOMEM;
    size_t cursor = 0;
    while (cursor < plen) {
        long start = sv_find(payload, plen, SOI, 2, cursor);
        if (start < 0)
            break;
        long end = sv_find(payload, plen, EOI, 2, (size_t)start);
        if (end < 0)
            break;
        end += 2;
        if (nj == cap) {
            cap *= 2;
            void *p = realloc(jpegs, cap * sizeof(*jpegs));
            if (!p) {
                free(jpegs);
                return SERVOOM_ERR_NOMEM;
            }
            jpegs = p;
        }
        jpegs[nj].off = (size_t)start;
        jpegs[nj].len = (size_t)(end - start);
        nj++;
        cursor = (size_t)end;
        if (cursor + 5 <= plen && memcmp(payload + cursor, GAP, 3) == 0)
            cursor += 5;
        if (total_frames && nj >= (size_t)total_frames)
            break;
    }
    if (nj == 0) {
        free(jpegs);
        return SERVOOM_ERR_CORRUPT; /* no JPEG frames extracted -> None */
    }

    /* _decode_jpeg_frames: stop at the first failure */
    servoom_pixel_bean *bean = sv_bean_new(41, (int)nj, speed ? speed : 50, row_count, column_count);
    if (!bean) {
        free(jpegs);
        return SERVOOM_ERR_NOMEM;
    }
    int count = 0;
    for (size_t i = 0; i < nj; i++) {
        uint8_t *rgb = NULL;
        int jw = 0, jh = 0;
        servoom_status st = sv_jpeg_decode_rgb(payload + jpegs[i].off, jpegs[i].len, &rgb, &jw, &jh);
        if (st == SERVOOM_ERR_NOMEM) {
            free(jpegs);
            servoom_pixel_bean_free(bean);
            return st;
        }
        if (st != SERVOOM_OK)
            break;
        uint8_t *dst = bean->frames + (size_t)count * frame_size;
        if (jw == width && jh == height) {
            memcpy(dst, rgb, frame_size);
        } else {
            uint8_t *r = sv_resize_nearest_rgb(rgb, jw, jh, width, height);
            if (!r) {
                free(rgb);
                free(jpegs);
                servoom_pixel_bean_free(bean);
                return SERVOOM_ERR_NOMEM;
            }
            memcpy(dst, r, frame_size);
            free(r);
        }
        free(rgb);
        count++;
    }
    free(jpegs);
    bean->total_frames = count;
    *out = bean;
    return SERVOOM_OK;
}
