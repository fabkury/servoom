/* MD5 (RFC 1321). Only used to hash the Divoom login password, like the Python client. */
#include "servoom/digest.h"

#include <string.h>

typedef struct {
    uint32_t a, b, c, d;
    uint64_t len;
    uint8_t buf[64];
    size_t buf_len;
} md5_ctx;

static const uint32_t S[64] = {7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
                               5, 9,  14, 20, 5, 9,  14, 20, 5, 9,  14, 20, 5, 9,  14, 20,
                               4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
                               6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21};

static const uint32_t T[64] = {
    0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee, 0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501,
    0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be, 0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821,
    0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa, 0xd62f105d, 0x02441453, 0xd8a1e681, 0xe7d3fbc8,
    0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed, 0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a,
    0xfffa3942, 0x8771f681, 0x6d9d6122, 0xfde5380c, 0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70,
    0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05, 0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665,
    0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039, 0x655b59c3, 0x8f0ccc92, 0xffeff47d, 0x85845dd1,
    0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1, 0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391};

#define ROTL(x, n) (((x) << (n)) | ((x) >> (32 - (n))))

static void md5_block(md5_ctx *ctx, const uint8_t *p)
{
    uint32_t m[16];
    for (int i = 0; i < 16; i++)
        m[i] = (uint32_t)p[i * 4] | ((uint32_t)p[i * 4 + 1] << 8) | ((uint32_t)p[i * 4 + 2] << 16) |
               ((uint32_t)p[i * 4 + 3] << 24);
    uint32_t a = ctx->a, b = ctx->b, c = ctx->c, d = ctx->d;
    for (uint32_t i = 0; i < 64; i++) {
        uint32_t f, g;
        if (i < 16) { f = (b & c) | (~b & d); g = i; }
        else if (i < 32) { f = (d & b) | (~d & c); g = (5 * i + 1) & 15; }
        else if (i < 48) { f = b ^ c ^ d; g = (3 * i + 5) & 15; }
        else { f = c ^ (b | ~d); g = (7 * i) & 15; }
        uint32_t tmp = d;
        d = c;
        c = b;
        b = b + ROTL(a + f + T[i] + m[g], S[i]);
        a = tmp;
    }
    ctx->a += a; ctx->b += b; ctx->c += c; ctx->d += d;
}

static void md5_update(md5_ctx *ctx, const uint8_t *p, size_t len)
{
    ctx->len += len;
    while (len > 0) {
        size_t take = 64 - ctx->buf_len;
        if (take > len)
            take = len;
        memcpy(ctx->buf + ctx->buf_len, p, take);
        ctx->buf_len += take;
        p += take;
        len -= take;
        if (ctx->buf_len == 64) {
            md5_block(ctx, ctx->buf);
            ctx->buf_len = 0;
        }
    }
}

void servoom_md5_hex(const void *data, size_t len, char hex[33])
{
    md5_ctx ctx = {0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476, 0, {0}, 0};
    md5_update(&ctx, (const uint8_t *)data, len);
    uint64_t bits = ctx.len * 8;
    uint8_t pad = 0x80;
    md5_update(&ctx, &pad, 1);
    uint8_t zero = 0;
    while (ctx.buf_len != 56)
        md5_update(&ctx, &zero, 1);
    uint8_t lenb[8];
    for (int i = 0; i < 8; i++)
        lenb[i] = (uint8_t)(bits >> (8 * i));
    md5_update(&ctx, lenb, 8);
    uint8_t digest[16];
    uint32_t words[4] = {ctx.a, ctx.b, ctx.c, ctx.d};
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 4; j++)
            digest[i * 4 + j] = (uint8_t)(words[i] >> (8 * j));
    servoom_digest_to_hex(digest, 16, hex);
}
