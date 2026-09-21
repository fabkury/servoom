/* Format 17 (0x11): one picture. Python PicMultiDecoder.
 *
 * [row u8][col u8][length BE32][AES-CBC ciphertext]; decrypted[:length] is an LZO1X stream
 * of the tiled RGB picture. Speed is fixed at 40 ms. */
#include "decoders/decoders.h"

#include <stdlib.h>
#include <string.h>
#include "codec/aes_cbc.h"
#include "codec/lzo1x.h"
#include "util/bytes.h"

servoom_status sv_decode_fmt17(const uint8_t *data, size_t len, servoom_pixel_bean **out)
{
    *out = NULL;
    if (len < 6)
        return SERVOOM_ERR_CORRUPT; /* struct.error */
    int row_count = data[0], column_count = data[1];
    uint32_t length = sv_be32(data + 2);
    size_t enc_len = len - 6;
    uint8_t *enc = sv_memdup(data + 6, enc_len);
    if (!enc)
        return SERVOOM_ERR_NOMEM;
    servoom_status st = sv_aes_divoom_decrypt(enc, enc_len);
    if (st != SERVOOM_OK) {
        free(enc);
        return st;
    }
    size_t take = length < enc_len ? length : enc_len; /* data[:length] clamps */
    size_t frame_size = (size_t)row_count * column_count * 256 * 3;
    uint8_t *raw = NULL;
    size_t raw_len = 0;
    st = sv_lzo1x_decompress(enc, take, frame_size, &raw, &raw_len);
    free(enc);
    if (st != SERVOOM_OK)
        return st;
    servoom_pixel_bean *bean = sv_bean_new(17, 1, 40, row_count, column_count);
    if (!bean) {
        free(raw);
        return SERVOOM_ERR_NOMEM;
    }
    st = sv_compact_frame(raw, raw_len, row_count, column_count, bean->frames);
    free(raw);
    if (st != SERVOOM_OK) {
        servoom_pixel_bean_free(bean);
        return st;
    }
    *out = bean;
    return SERVOOM_OK;
}
