/* Format 18 (0x12): 32x32 / 64x64 animation. Python AnimMultiDecoder.
 *
 * [frames u8][speed BE16][row u8][col u8][AES-CBC ciphertext]; the plaintext is a sequence
 * of [size BE32][LZO1X stream] records, one per frame, each inflating to a tiled RGB frame. */
#include "decoders/decoders.h"

#include <stdlib.h>
#include <string.h>
#include "codec/aes_cbc.h"
#include "codec/lzo1x.h"
#include "util/bytes.h"

servoom_status sv_decode_fmt18(const uint8_t *data, size_t len, servoom_pixel_bean **out)
{
    *out = NULL;
    if (len < 5)
        return SERVOOM_ERR_CORRUPT;
    int total_frames = data[0];
    int speed = sv_be16(data + 1);
    int row_count = data[3], column_count = data[4];
    size_t enc_len = len - 5;
    uint8_t *plain = sv_memdup(data + 5, enc_len);
    if (!plain)
        return SERVOOM_ERR_NOMEM;
    servoom_status st = sv_aes_divoom_decrypt(plain, enc_len);
    if (st != SERVOOM_OK) {
        free(plain);
        return st;
    }
    size_t frame_size = (size_t)row_count * column_count * 256 * 3;
    servoom_pixel_bean *bean = sv_bean_new(18, total_frames, speed, row_count, column_count);
    if (!bean) {
        free(plain);
        return SERVOOM_ERR_NOMEM;
    }
    size_t pos = 0;
    for (int f = 0; f < total_frames; f++) {
        if (enc_len - pos < 4) { /* unpack('>I') on a short slice -> struct.error */
            st = SERVOOM_ERR_CORRUPT;
            goto fail;
        }
        uint32_t size = sv_be32(plain + pos);
        pos += 4;
        size_t avail = enc_len - pos;
        size_t take = size < avail ? size : avail; /* Python slice clamps */
        uint8_t *raw = NULL;
        size_t raw_len = 0;
        st = sv_lzo1x_decompress(plain + pos, take, frame_size, &raw, &raw_len);
        if (st != SERVOOM_OK)
            goto fail;
        pos += size; /* Python advances by the declared size even past the end */
        if (pos > enc_len)
            pos = enc_len;
        st = sv_compact_frame(raw, raw_len, row_count, column_count,
                              bean->frames + (size_t)f * frame_size);
        free(raw);
        if (st != SERVOOM_OK)
            goto fail;
    }
    free(plain);
    *out = bean;
    return SERVOOM_OK;
fail:
    free(plain);
    servoom_pixel_bean_free(bean);
    return st;
}
