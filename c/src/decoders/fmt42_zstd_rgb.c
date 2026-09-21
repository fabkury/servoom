/* Format 42 (0x2A): zstd-compressed raw RGB frames. Python AnimZstdRawRGBDecoder. */
#include "decoders/decoders.h"

#include <stdlib.h>
#include <string.h>
#include "codec/zstd_util.h"
#include "util/bytes.h"

servoom_status sv_decode_fmt42(const uint8_t *data, size_t len, servoom_pixel_bean **out)
{
    *out = NULL;
    if (len < 5)
        return SERVOOM_ERR_CORRUPT;
    int total_frames = data[0];
    int speed = sv_be16(data + 1);
    int row_count = data[3], column_count = data[4];
    int width = column_count * 16, height = row_count * 16;
    const uint8_t *rest = data + 5;
    size_t rest_len = len - 5;
    long idx = sv_find(rest, rest_len, (const uint8_t *)SV_ZSTD_MAGIC, 4, 0);
    if (idx < 0)
        return SERVOOM_ERR_CORRUPT; /* 'zstd magic not found' */
    uint8_t *raw = NULL;
    size_t raw_len = 0;
    /* ZstdDecompressor().decompress(payload): strict one-shot semantics. */
    servoom_status st = sv_zstd_decompress(rest + idx, rest_len - (size_t)idx, 1, 0, &raw, &raw_len);
    if (st != SERVOOM_OK)
        return st;
    size_t frame_bytes = (size_t)width * height * 3;
    if (frame_bytes == 0) {
        free(raw);
        return SERVOOM_ERR_CORRUPT; /* 'Invalid dimensions' */
    }
    size_t available = raw_len / frame_bytes;
    int target = (int)(available < (size_t)total_frames ? available : (size_t)total_frames);
    servoom_pixel_bean *bean = sv_bean_new(42, target, speed, row_count, column_count);
    if (!bean) {
        free(raw);
        return SERVOOM_ERR_NOMEM;
    }
    memcpy(bean->frames, raw, frame_bytes * (size_t)target);
    free(raw);
    *out = bean;
    return SERVOOM_OK;
}
