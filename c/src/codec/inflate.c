/* zlib / DEFLATE decoder (RFC 1950 + 1951), written for the 0x1D layer container.
 *
 * Canonical Huffman decoding one bit at a time (count/symbol tables, the "puff" way):
 * simple, obviously correct, and fast enough for layer payloads of a few megabytes. */
#include "codec/inflate.h"

#include <stdlib.h>
#include <string.h>

#define MAXBITS 15
#define MAXLCODES 286
#define MAXDCODES 30
#define MAXCODES (MAXLCODES + MAXDCODES)
#define FIXLCODES 288

typedef struct {
    const uint8_t *in;
    size_t in_len, in_pos;
    uint32_t bitbuf;
    int bitcnt;
    uint8_t *out;
    size_t out_len, out_cap, max_out;
    int err; /* sticky: 1 = corrupt/truncated input, 2 = out of memory, 3 = output cap */
} inf_state;

typedef struct {
    short count[MAXBITS + 1]; /* number of codes of each length */
    short symbol[FIXLCODES]; /* symbols ordered by code */
} huffman;

static int bits(inf_state *s, int need)
{
    uint32_t val = s->bitbuf;
    while (s->bitcnt < need) {
        if (s->in_pos >= s->in_len) {
            s->err = 1;
            return 0;
        }
        val |= (uint32_t)s->in[s->in_pos++] << s->bitcnt;
        s->bitcnt += 8;
    }
    s->bitbuf = val >> need;
    s->bitcnt -= need;
    return (int)(val & ((1u << need) - 1));
}

static int put(inf_state *s, const uint8_t *src, size_t n)
{
    if (s->max_out && s->out_len + n > s->max_out) {
        s->err = 3;
        return -1;
    }
    if (s->out_len + n > s->out_cap) {
        size_t ncap = s->out_cap ? s->out_cap : 4096;
        while (ncap < s->out_len + n)
            ncap *= 2;
        uint8_t *grown = (uint8_t *)realloc(s->out, ncap);
        if (!grown) {
            s->err = 2;
            return -1;
        }
        s->out = grown;
        s->out_cap = ncap;
    }
    memcpy(s->out + s->out_len, src, n);
    s->out_len += n;
    return 0;
}

/* Build a canonical Huffman table from `n` code lengths. Returns 0 for a complete code,
 * > 0 for an incomplete one (allowed only for a single-code distance table), < 0 when
 * over-subscribed. */
static int construct(huffman *h, const short *length, int n)
{
    short offs[MAXBITS + 1];
    int sym, len, left;
    for (len = 0; len <= MAXBITS; len++)
        h->count[len] = 0;
    for (sym = 0; sym < n; sym++)
        h->count[length[sym]]++;
    if (h->count[0] == n)
        return 0; /* no codes at all */
    left = 1;
    for (len = 1; len <= MAXBITS; len++) {
        left <<= 1;
        left -= h->count[len];
        if (left < 0)
            return left;
    }
    offs[1] = 0;
    for (len = 1; len < MAXBITS; len++)
        offs[len + 1] = (short)(offs[len] + h->count[len]);
    for (sym = 0; sym < n; sym++)
        if (length[sym] != 0)
            h->symbol[offs[length[sym]]++] = (short)sym;
    return left;
}

static int decode(inf_state *s, const huffman *h)
{
    int len, code = 0, first = 0, index = 0;
    for (len = 1; len <= MAXBITS; len++) {
        code |= bits(s, 1);
        if (s->err)
            return -1;
        int count = h->count[len];
        if (code - count < first)
            return h->symbol[index + (code - first)];
        index += count;
        first += count;
        first <<= 1;
        code <<= 1;
    }
    s->err = 1; /* ran out of codes */
    return -1;
}

static const short LBASE[29] = {3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
                                35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258};
static const short LEXT[29] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
                               3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0};
static const short DBASE[30] = {1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
                                257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145,
                                8193, 12289, 16385, 24577};
static const short DEXT[30] = {0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6,
                               7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13};

/* Decode literal/length + distance codes until end-of-block. */
static int codes(inf_state *s, const huffman *lencode, const huffman *distcode)
{
    for (;;) {
        int sym = decode(s, lencode);
        if (sym < 0)
            return -1;
        if (sym < 256) {
            uint8_t b = (uint8_t)sym;
            if (put(s, &b, 1))
                return -1;
        } else if (sym == 256) {
            return 0;
        } else {
            sym -= 257;
            if (sym >= 29) {
                s->err = 1;
                return -1;
            }
            int len = LBASE[sym] + bits(s, LEXT[sym]);
            int dsym = decode(s, distcode);
            if (dsym < 0 || dsym >= 30 || s->err) {
                s->err = 1;
                return -1;
            }
            size_t dist = (size_t)DBASE[dsym] + (size_t)bits(s, DEXT[dsym]);
            if (s->err)
                return -1;
            if (dist > s->out_len) {
                s->err = 1; /* distance before the start of the output */
                return -1;
            }
            /* byte-by-byte copy: the source may overlap the bytes being written */
            for (int i = 0; i < len; i++) {
                uint8_t b = s->out[s->out_len - dist];
                if (put(s, &b, 1))
                    return -1;
            }
        }
    }
}

static int stored(inf_state *s)
{
    s->bitbuf = 0;
    s->bitcnt = 0; /* discard the bits left in the current byte */
    if (s->in_pos + 4 > s->in_len) {
        s->err = 1;
        return -1;
    }
    unsigned len = s->in[s->in_pos] | ((unsigned)s->in[s->in_pos + 1] << 8);
    unsigned nlen = s->in[s->in_pos + 2] | ((unsigned)s->in[s->in_pos + 3] << 8);
    s->in_pos += 4;
    if (len != (~nlen & 0xffffu) || s->in_pos + len > s->in_len) {
        s->err = 1;
        return -1;
    }
    if (put(s, s->in + s->in_pos, len))
        return -1;
    s->in_pos += len;
    return 0;
}

static int fixed(inf_state *s)
{
    static int built = 0;
    static huffman lencode, distcode;
    if (!built) {
        short lengths[FIXLCODES];
        int sym;
        for (sym = 0; sym < 144; sym++)
            lengths[sym] = 8;
        for (; sym < 256; sym++)
            lengths[sym] = 9;
        for (; sym < 280; sym++)
            lengths[sym] = 7;
        for (; sym < FIXLCODES; sym++)
            lengths[sym] = 8;
        construct(&lencode, lengths, FIXLCODES);
        for (sym = 0; sym < MAXDCODES; sym++)
            lengths[sym] = 5;
        construct(&distcode, lengths, MAXDCODES);
        built = 1;
    }
    return codes(s, &lencode, &distcode);
}

static int dynamic(inf_state *s)
{
    static const short order[19] = {16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15};
    short lengths[MAXCODES];
    huffman lencode, distcode;
    int nlen = bits(s, 5) + 257, ndist = bits(s, 5) + 1, ncode = bits(s, 4) + 4, index;
    if (s->err || nlen > MAXLCODES || ndist > MAXDCODES) {
        s->err = 1;
        return -1;
    }
    for (index = 0; index < ncode; index++)
        lengths[order[index]] = (short)bits(s, 3);
    for (; index < 19; index++)
        lengths[order[index]] = 0;
    if (s->err || construct(&lencode, lengths, 19) != 0) {
        s->err = 1;
        return -1;
    }
    index = 0;
    while (index < nlen + ndist) {
        int sym = decode(s, &lencode);
        if (sym < 0)
            return -1;
        if (sym < 16) {
            lengths[index++] = (short)sym;
        } else {
            short len = 0;
            int rep;
            if (sym == 16) {
                if (index == 0) {
                    s->err = 1;
                    return -1;
                }
                len = lengths[index - 1];
                rep = 3 + bits(s, 2);
            } else if (sym == 17) {
                rep = 3 + bits(s, 3);
            } else {
                rep = 11 + bits(s, 7);
            }
            if (s->err || index + rep > nlen + ndist) {
                s->err = 1;
                return -1;
            }
            while (rep--)
                lengths[index++] = len;
        }
    }
    if (lengths[256] == 0) {
        s->err = 1; /* no end-of-block code */
        return -1;
    }
    int err = construct(&lencode, lengths, nlen);
    if (err < 0 || (err > 0 && nlen - lencode.count[0] != 1)) {
        s->err = 1;
        return -1;
    }
    err = construct(&distcode, lengths + nlen, ndist);
    if (err < 0 || (err > 0 && ndist - distcode.count[0] != 1)) {
        s->err = 1;
        return -1;
    }
    return codes(s, &lencode, &distcode);
}

static uint32_t adler32(const uint8_t *data, size_t len)
{
    uint32_t a = 1, b = 0;
    for (size_t i = 0; i < len; i++) {
        a = (a + data[i]) % 65521u;
        b = (b + a) % 65521u;
    }
    return (b << 16) | a;
}

servoom_status sv_zlib_inflate(const uint8_t *in, size_t in_len, size_t expected_out,
                               size_t max_out, uint8_t **out, size_t *out_len)
{
    if (!out || !out_len)
        return SERVOOM_ERR_ARG;
    *out = NULL;
    *out_len = 0;
    if (!in || in_len < 6)
        return SERVOOM_ERR_CODEC;
    unsigned cmf = in[0], flg = in[1];
    if ((cmf & 0x0f) != 8 || (cmf >> 4) > 7 || ((cmf << 8) | flg) % 31 != 0 || (flg & 0x20))
        return SERVOOM_ERR_CODEC; /* not deflate, bad window, bad check, or preset dictionary */

    inf_state s;
    memset(&s, 0, sizeof s);
    s.in = in + 2;
    s.in_len = in_len - 2;
    s.max_out = max_out;
    if (expected_out) {
        s.out = (uint8_t *)malloc(expected_out);
        if (!s.out)
            return SERVOOM_ERR_NOMEM;
        s.out_cap = expected_out;
    }
    int last;
    do {
        last = bits(&s, 1);
        int type = bits(&s, 2);
        if (s.err)
            break;
        if (type == 0)
            stored(&s);
        else if (type == 1)
            fixed(&s);
        else if (type == 2)
            dynamic(&s);
        else
            s.err = 1;
    } while (!last && !s.err);
    if (s.err) {
        free(s.out);
        return s.err == 2 ? SERVOOM_ERR_NOMEM : SERVOOM_ERR_CODEC;
    }
    /* Adler-32 trailer, big-endian, after the last (partial) byte of deflate data. */
    if (s.in_pos + 4 > s.in_len) {
        free(s.out);
        return SERVOOM_ERR_CODEC;
    }
    uint32_t want = ((uint32_t)s.in[s.in_pos] << 24) | ((uint32_t)s.in[s.in_pos + 1] << 16) |
                    ((uint32_t)s.in[s.in_pos + 2] << 8) | s.in[s.in_pos + 3];
    if (adler32(s.out, s.out_len) != want) {
        free(s.out);
        return SERVOOM_ERR_CODEC;
    }
    if (!s.out) { /* empty stream */
        s.out = (uint8_t *)malloc(1);
        if (!s.out)
            return SERVOOM_ERR_NOMEM;
    }
    *out = s.out;
    *out_len = s.out_len;
    return SERVOOM_OK;
}
