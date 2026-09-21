/* AES-128-CBC decryption with the Divoom fixed key/IV (tiny-AES-c underneath). */
#ifndef SERVOOM_CODEC_AES_CBC_H
#define SERVOOM_CODEC_AES_CBC_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

/* Decrypt `len` bytes in place with the Divoom key ("78hrey23y28ogs89") and IV
 * ("1234567890123456"). `len` must be a multiple of 16 (PyCryptodome raises otherwise; we
 * return SERVOOM_ERR_CODEC). No padding is removed, exactly like the Python code. */
servoom_status sv_aes_divoom_decrypt(uint8_t *data, size_t len);

#endif
