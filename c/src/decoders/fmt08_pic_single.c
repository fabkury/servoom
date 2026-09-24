/* Format 8 (0x08): a single 16x16 picture. Python PicSingleDecoder.
 *
 * File: [0x08][AES-CBC ciphertext of one raw 16x16 RGB frame (768 bytes)]. The still
 * sibling of format 9, without format 9's speed prefix: every live sample is 769 bytes.
 * The ciphertext is truncated to a multiple of 16 and only the first 768 decrypted bytes
 * are used; the bean reports one frame at speed 40 (as format 17 does). */
#include "decoders/decoders.h"

#include <stdlib.h>
#include <string.h>
#include "codec/aes_cbc.h"
#include "util/bytes.h"

servoom_status sv_decode_fmt08(const uint8_t *data, size_t len, servoom_pixel_bean **out)
{
    *out = NULL;
    size_t usable = len - (len % 16);
    if (usable < 768)
        return SERVOOM_ERR_CORRUPT;
    uint8_t *enc = sv_memdup(data, usable);
    if (!enc)
        return SERVOOM_ERR_NOMEM;
    servoom_status st = sv_aes_divoom_decrypt(enc, usable);
    if (st != SERVOOM_OK) {
        free(enc);
        return st;
    }
    servoom_pixel_bean *bean = sv_bean_new(8, 1, 40, 1, 1);
    if (!bean) {
        free(enc);
        return SERVOOM_ERR_NOMEM;
    }
    st = sv_compact_frame(enc, 768, 1, 1, bean->frames);
    free(enc);
    if (st != SERVOOM_OK) {
        servoom_pixel_bean_free(bean);
        return st;
    }
    *out = bean;
    return SERVOOM_OK;
}
