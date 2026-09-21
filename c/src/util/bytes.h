/* Byte-level helpers: big-endian readers, a growable byte buffer, memmem. */
#ifndef SERVOOM_UTIL_BYTES_H
#define SERVOOM_UTIL_BYTES_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

static inline uint16_t sv_be16(const uint8_t *p) { return (uint16_t)((p[0] << 8) | p[1]); }
static inline uint32_t sv_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}
static inline uint16_t sv_le16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }

/* Growable byte buffer. */
typedef struct sv_buf {
    uint8_t *data;
    size_t len;
    size_t cap;
} sv_buf;

void sv_buf_init(sv_buf *b);
void sv_buf_free(sv_buf *b);
servoom_status sv_buf_reserve(sv_buf *b, size_t cap);
servoom_status sv_buf_append(sv_buf *b, const void *data, size_t len);
servoom_status sv_buf_append_byte(sv_buf *b, uint8_t byte);
/* Detach the storage (caller frees); the buffer is reset to empty. */
uint8_t *sv_buf_detach(sv_buf *b, size_t *len);

/* First occurrence of `needle` in `hay` at or after `from`; returns -1 if absent. */
long sv_find(const uint8_t *hay, size_t hay_len, const uint8_t *needle, size_t needle_len,
             size_t from);

/* malloc + memcpy of `len` bytes (NULL on OOM). */
uint8_t *sv_memdup(const void *src, size_t len);

/* Duplicate a C string (NULL on OOM or NULL input). */
char *sv_strdup(const char *s);

#endif
