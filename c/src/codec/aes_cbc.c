#include "codec/aes_cbc.h"

#include <string.h>
#include "aes.h"

static const uint8_t DIVOOM_KEY[16] = {'7', '8', 'h', 'r', 'e', 'y', '2', '3',
                                       'y', '2', '8', 'o', 'g', 's', '8', '9'};
static const uint8_t DIVOOM_IV[16] = {'1', '2', '3', '4', '5', '6', '7', '8',
                                      '9', '0', '1', '2', '3', '4', '5', '6'};

servoom_status sv_aes_divoom_decrypt(uint8_t *data, size_t len)
{
    if (len % 16 != 0)
        return SERVOOM_ERR_CODEC;
    if (len == 0)
        return SERVOOM_OK;
    struct AES_ctx ctx;
    AES_init_ctx_iv(&ctx, DIVOOM_KEY, DIVOOM_IV);
    AES_CBC_decrypt_buffer(&ctx, data, len);
    return SERVOOM_OK;
}
