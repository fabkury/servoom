/* Small digest helpers exposed because callers need them: MD5 for the Divoom login
 * password, SHA-256 for verifying decoded output against the reference baseline. */
#ifndef SERVOOM_DIGEST_H
#define SERVOOM_DIGEST_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct servoom_sha256 {
    uint32_t state[8];
    uint64_t bitlen;
    uint8_t buffer[64];
    size_t buffer_len;
} servoom_sha256;

void servoom_sha256_init(servoom_sha256 *ctx);
void servoom_sha256_update(servoom_sha256 *ctx, const void *data, size_t len);
void servoom_sha256_final(servoom_sha256 *ctx, uint8_t digest[32]);
/* One-shot: lowercase hex into `hex` (65 bytes incl. NUL). */
void servoom_sha256_hex(const void *data, size_t len, char hex[65]);
void servoom_digest_to_hex(const uint8_t *digest, size_t len, char *hex);

/* MD5 of `len` bytes; `hex` receives 32 lowercase hex chars + NUL. */
void servoom_md5_hex(const void *data, size_t len, char hex[33]);

#ifdef __cplusplus
}
#endif
#endif
