#include "codec/lzo1x.h"

#include <stdlib.h>
#include <string.h>
#include "util/bytes.h"

/* The LZO1X stream grammar (as produced by lzo1x_1_compress and friends):
 *
 *   first byte > 17            -> literal run of (byte - 17) bytes
 *   0..15  : literal run       -> length = t + 3, with zero-byte length extension
 *   16..31 : match, 3-byte     -> distance 16384 + 14 bits, length from low 3 bits (+ext)
 *   32..63 : match, 2-byte     -> distance 1 + 14 bits, length from low 5 bits (+ext)
 *   64..255: match, 2 bytes    -> distance 1 + 3 bits + 8 bits, length 3..8
 *   after a match, the low 2 bits of the second-to-last consumed byte give 0..3 trailing
 *   literals; the end marker is a 16..31 code with a zero distance (bytes 11 00 00).
 */

#define NEED_IN(n)                                                                     \
    do {                                                                               \
        if ((size_t)(in_len - ip) < (size_t)(n))                                       \
            goto input_overrun;                                                        \
    } while (0)

#define PUT(byte)                                                                      \
    do {                                                                               \
        if (op == cap) {                                                               \
            size_t ncap = cap ? cap * 2 : 4096;                                        \
            uint8_t *np = (uint8_t *)realloc(outp, ncap);                              \
            if (!np)                                                                   \
                goto nomem;                                                            \
            outp = np;                                                                 \
            cap = ncap;                                                                \
        }                                                                              \
        outp[op++] = (uint8_t)(byte);                                                  \
    } while (0)

servoom_status sv_lzo1x_decompress(const uint8_t *in, size_t in_len, size_t size_hint,
                                   uint8_t **out, size_t *out_len)
{
    uint8_t *outp = NULL;
    size_t cap = 0, op = 0, ip = 0;
    size_t t, m_pos;
    servoom_status st = SERVOOM_ERR_CODEC;

    *out = NULL;
    *out_len = 0;
    if (in_len == 0)
        return SERVOOM_ERR_CODEC;
    if (size_hint) {
        outp = (uint8_t *)malloc(size_hint);
        if (!outp)
            return SERVOOM_ERR_NOMEM;
        cap = size_hint;
    }

    if (in[ip] > 17) {
        t = (size_t)in[ip++] - 17;
        if (t < 4)
            goto match_next;
        NEED_IN(t);
        while (t-- > 0)
            PUT(in[ip++]);
        goto first_literal_run;
    }

    for (;;) {
        NEED_IN(1);
        t = in[ip++];
        if (t >= 16)
            goto match;
        if (t == 0) {
            for (;;) {
                NEED_IN(1);
                if (in[ip] != 0)
                    break;
                t += 255;
                ip++;
            }
            t += 15 + in[ip++];
        }
        t += 3;
        NEED_IN(t);
        while (t-- > 0)
            PUT(in[ip++]);

    first_literal_run:
        NEED_IN(1);
        t = in[ip++];
        if (t >= 16)
            goto match;
        /* short match right after a literal run */
        NEED_IN(1);
        m_pos = (1 + 0x0800) + (t >> 2) + ((size_t)in[ip++] << 2);
        if (m_pos > op)
            goto lookbehind_overrun;
        m_pos = op - m_pos;
        PUT(outp[m_pos]); PUT(outp[m_pos + 1]); PUT(outp[m_pos + 2]);
        goto match_done;

        for (;;) {
        match:
            if (t >= 64) {
                NEED_IN(1);
                m_pos = 1 + ((t >> 2) & 7) + ((size_t)in[ip++] << 3);
                t = (t >> 5) - 1;
            } else if (t >= 32) {
                t &= 31;
                if (t == 0) {
                    for (;;) {
                        NEED_IN(1);
                        if (in[ip] != 0)
                            break;
                        t += 255;
                        ip++;
                    }
                    t += 31 + in[ip++];
                }
                NEED_IN(2);
                m_pos = 1 + (in[ip] >> 2) + ((size_t)in[ip + 1] << 6);
                ip += 2;
            } else if (t >= 16) {
                size_t high = (t & 8) << 11;
                t &= 7;
                if (t == 0) {
                    for (;;) {
                        NEED_IN(1);
                        if (in[ip] != 0)
                            break;
                        t += 255;
                        ip++;
                    }
                    t += 7 + in[ip++];
                }
                NEED_IN(2);
                m_pos = high + (in[ip] >> 2) + ((size_t)in[ip + 1] << 6);
                ip += 2;
                if (m_pos == 0)
                    goto eof_found;
                m_pos += 0x4000;
            } else {
                NEED_IN(1);
                m_pos = 1 + (t >> 2) + ((size_t)in[ip++] << 2);
                if (m_pos > op)
                    goto lookbehind_overrun;
                m_pos = op - m_pos;
                PUT(outp[m_pos]); PUT(outp[m_pos + 1]);
                goto match_done;
            }
            /* copy_match: t + 2 bytes from op - m_pos (may overlap) */
            if (m_pos > op)
                goto lookbehind_overrun;
            m_pos = op - m_pos;
            t += 2;
            while (t-- > 0) {
                uint8_t b = outp[m_pos++];
                PUT(b);
            }

        match_done:
            t = in[ip - 2] & 3;
            if (t == 0)
                break;
        match_next:
            NEED_IN(t);
            while (t-- > 0)
                PUT(in[ip++]);
            NEED_IN(1);
            t = in[ip++];
        }
    }

eof_found:
    if (ip != in_len) {
        /* Trailing garbage is tolerated by lzallright only when it is exactly the stream
         * end; anything else is an error there too. Be strict. */
        st = SERVOOM_ERR_CODEC;
        goto fail;
    }
    *out = outp ? outp : (uint8_t *)malloc(1);
    *out_len = op;
    return *out ? SERVOOM_OK : SERVOOM_ERR_NOMEM;

input_overrun:
lookbehind_overrun:
    st = SERVOOM_ERR_CODEC;
    goto fail;
nomem:
    st = SERVOOM_ERR_NOMEM;
fail:
    free(outp);
    return st;
}
