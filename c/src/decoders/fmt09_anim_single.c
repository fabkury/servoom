/* Format 9 (0x09): 16x16 animation. Python AnimSingleDecoder.
 *
 * File: [0x09][?][speed BE16][... AES-CBC ciphertext ...]. The Python code prepends a
 * zero byte to the post-format-byte data, takes speed from content[2:4] and decrypts
 * content[4:] (i.e. file[4:]); every 768 decrypted bytes is one 16x16 RGB frame. */
#include "decoders/decoders.h"

#include <stdlib.h>
#include <string.h>
#include "codec/aes_cbc.h"
#include "util/bytes.h"

servoom_status sv_decode_fmt09(const uint8_t *data, size_t len, servoom_pixel_bean **out)
{
    *out = NULL;
    /* content = b'\x00' + data, so len(content) = len + 1; needs >= 4 (bytearray(n-4)). */
    if (len + 1 < 4)
        return SERVOOM_ERR_CORRUPT;
    int speed = sv_be16(data + 1); /* content[2:4] == data[1:3] */
    size_t enc_len = len + 1 - 4;
    uint8_t *enc = sv_memdup(data + 3, enc_len);
    if (!enc)
        return SERVOOM_ERR_NOMEM;
    servoom_status st = sv_aes_divoom_decrypt(enc, enc_len);
    if (st != SERVOOM_OK) {
        free(enc);
        return st;
    }
    int total_frames = (int)(enc_len / 768);
    servoom_pixel_bean *bean = sv_bean_new(9, total_frames, speed, 1, 1);
    if (!bean) {
        free(enc);
        return SERVOOM_ERR_NOMEM;
    }
    for (int i = 0; i < total_frames; i++) {
        st = sv_compact_frame(enc + (size_t)i * 768, 768, 1, 1, bean->frames + (size_t)i * 768);
        if (st != SERVOOM_OK) {
            free(enc);
            servoom_pixel_bean_free(bean);
            return st;
        }
    }
    free(enc);
    *out = bean;
    return SERVOOM_OK;
}
