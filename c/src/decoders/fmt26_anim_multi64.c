/* Format 26 (0x1A), 64x64 canvas: quantized-palette (0x0C) frames. Python
 * AnimMulti64Decoder. Also the format-26 dispatcher (Python _decode_format_26). */
#include "decoders/decoders.h"

#include <stdlib.h>
#include <string.h>
#include "util/bytes.h"

servoom_status sv_decode_fmt26(const uint8_t *data, size_t len, servoom_pixel_bean **out)
{
    *out = NULL;
    if (len < 5)
        return SERVOOM_ERR_CORRUPT; /* Python returns None */
    int width = data[4] * 16, height = data[3] * 16;
    if (width == 64 && height == 64)
        return sv_decode_fmt26_multi64(data, data + 5, len - 5, out);
    return sv_decode_fmt26_hier(data, data + 5, len - 5, out);
}

servoom_status sv_decode_fmt26_multi64(const uint8_t *hdr, const uint8_t *body, size_t body_len,
                                       servoom_pixel_bean **out)
{
    *out = NULL;
    int total_declared = hdr[0];
    int speed = sv_be16(hdr + 1);
    int row_count = hdr[3], column_count = hdr[4];
    /* _decode_0x0c_frame always emits 4096 pixels = 12288 bytes, then _compact tiles them
     * into the 4x4-tile canvas. */
    uint8_t *raw = (uint8_t *)malloc(12288);
    if (!raw)
        return SERVOOM_ERR_NOMEM;
    servoom_pixel_bean *bean = sv_bean_new(26, total_declared, speed, row_count, column_count);
    if (!bean) {
        free(raw);
        return SERVOOM_ERR_NOMEM;
    }
    size_t frame_size = (size_t)bean->width * bean->height * 3;
    size_t pos = 0;
    int decoded = 0;
    servoom_status st = SERVOOM_OK;
    for (int f = 0; f < total_declared; f++) {
        if (body_len - pos < 4)
            break;
        uint32_t size = sv_be32(body + pos);
        pos += 4;
        if (body_len - pos < size)
            break;
        st = sv_decode_0x0c_frame(body + pos, size, 4096, raw);
        if (st != SERVOOM_OK)
            goto fail; /* exception propagates out of AnimMulti64Decoder */
        pos += size;
        st = sv_compact_frame(raw, 12288, row_count, column_count,
                              bean->frames + (size_t)decoded * frame_size);
        if (st != SERVOOM_OK)
            goto fail;
        decoded++;
    }
    free(raw);
    bean->total_frames = decoded;
    *out = bean;
    return SERVOOM_OK;
fail:
    free(raw);
    servoom_pixel_bean_free(bean);
    return st;
}
