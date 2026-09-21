#include "util/bytes.h"

#include <stdlib.h>
#include <string.h>

void sv_buf_init(sv_buf *b)
{
    b->data = NULL;
    b->len = 0;
    b->cap = 0;
}

void sv_buf_free(sv_buf *b)
{
    free(b->data);
    sv_buf_init(b);
}

servoom_status sv_buf_reserve(sv_buf *b, size_t cap)
{
    if (cap <= b->cap)
        return SERVOOM_OK;
    size_t new_cap = b->cap ? b->cap : 256;
    while (new_cap < cap) {
        if (new_cap > ((size_t)-1) / 2)
            return SERVOOM_ERR_NOMEM;
        new_cap *= 2;
    }
    uint8_t *p = (uint8_t *)realloc(b->data, new_cap);
    if (!p)
        return SERVOOM_ERR_NOMEM;
    b->data = p;
    b->cap = new_cap;
    return SERVOOM_OK;
}

servoom_status sv_buf_append(sv_buf *b, const void *data, size_t len)
{
    if (len == 0)
        return SERVOOM_OK;
    if (b->len > ((size_t)-1) - len)
        return SERVOOM_ERR_NOMEM;
    servoom_status st = sv_buf_reserve(b, b->len + len);
    if (st != SERVOOM_OK)
        return st;
    memcpy(b->data + b->len, data, len);
    b->len += len;
    return SERVOOM_OK;
}

servoom_status sv_buf_append_byte(sv_buf *b, uint8_t byte)
{
    return sv_buf_append(b, &byte, 1);
}

uint8_t *sv_buf_detach(sv_buf *b, size_t *len)
{
    uint8_t *p = b->data;
    if (len)
        *len = b->len;
    sv_buf_init(b);
    return p;
}

long sv_find(const uint8_t *hay, size_t hay_len, const uint8_t *needle, size_t needle_len,
             size_t from)
{
    if (needle_len == 0)
        return from <= hay_len ? (long)from : -1;
    if (hay_len < needle_len)
        return -1;
    for (size_t i = from; i + needle_len <= hay_len; i++) {
        if (hay[i] == needle[0] && memcmp(hay + i, needle, needle_len) == 0)
            return (long)i;
    }
    return -1;
}

uint8_t *sv_memdup(const void *src, size_t len)
{
    uint8_t *p = (uint8_t *)malloc(len ? len : 1);
    if (!p)
        return NULL;
    if (len)
        memcpy(p, src, len);
    return p;
}

char *sv_strdup(const char *s)
{
    if (!s)
        return NULL;
    size_t n = strlen(s) + 1;
    char *p = (char *)malloc(n);
    if (p)
        memcpy(p, s, n);
    return p;
}
