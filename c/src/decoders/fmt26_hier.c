/* Format 26 (0x1A) for canvases other than 64x64 (in practice 128x128): Python
 * Decoder0x1A + _Decoder0x1AFrame.
 *
 * Each frame is [size BE32][0xAA payload]. The payload header is
 *   AA | len LE16 | ? | ? | encrypt_type | palette_size LE16 | palette RGB... | pixels
 * encrypt types: 0x11 raw RGB, 0x13 palette delta (append to the previous frame's palette),
 * 0x15 full palette. Pixels are a quadtree: 64x64 quadrants -> 32 -> 16 -> 8 blocks, each
 * node either "raw indices into the parent's map" (ctrl 0), "raw indices into a masked
 * subset" (ctrl 2) or "recurse with a masked subset" (anything else); 8x8 leaves use a
 * one-byte header with bit 7 = mask present. Indices are LSB-first bit fields.
 *
 * A file may also carry 0x0C frames; Decoder0x1A detects that by probing the first frame
 * and then decodes them with the 4096-pixel 0x0C routine, zero-padding to the canvas
 * (yes: on a 128x128 canvas only the top quarter gets pixels -- that is what the Python
 * code does, and parity is the contract). */
#include "decoders/decoders.h"

#include <stdlib.h>
#include <string.h>
#include "util/bytes.h"

/* ------------------------------------------------------------------------- */
/* Per-frame hierarchical decoder                                            */
/* ------------------------------------------------------------------------- */
typedef struct {
    uint8_t (*palette)[3];
    int palette_len;
    int palette_cap;
} palette_t;

typedef struct {
    const uint8_t *pixel;
    size_t pixel_len;
    palette_t *pal;
    int base_bpp;
    int width, height;
    uint8_t *out; /* width*height*3, black initially */
    size_t out_px;
    int failed;   /* an IndexError/ValueError happened */
    uint32_t *values; /* scratch, 4096 entries */
} frame_t;

static int bits_from_count(int n)
{
    if (n <= 1)
        return 0;
    int bits = 1;
    while ((1 << bits) < n)
        bits++;
    return bits;
}

static servoom_status palette_push(palette_t *p, uint8_t r, uint8_t g, uint8_t b)
{
    if (p->palette_len == p->palette_cap) {
        int ncap = p->palette_cap ? p->palette_cap * 2 : 256;
        uint8_t(*np)[3] = (uint8_t(*)[3])realloc(p->palette, (size_t)ncap * 3);
        if (!np)
            return SERVOOM_ERR_NOMEM;
        p->palette = np;
        p->palette_cap = ncap;
    }
    p->palette[p->palette_len][0] = r;
    p->palette[p->palette_len][1] = g;
    p->palette[p->palette_len][2] = b;
    p->palette_len++;
    return SERVOOM_OK;
}

/* _palette_at: out-of-range -> entry 0; empty palette -> IndexError. */
static int paint(frame_t *f, size_t out_index, int idx)
{
    if (!(idx >= 0 && idx < f->pal->palette_len))
        idx = 0;
    if (f->pal->palette_len == 0)
        return 0; /* palette[0] on an empty list -> IndexError */
    if (out_index >= f->out_px)
        return 0; /* self.out[...] = ... -> IndexError */
    memcpy(f->out + out_index * 3, f->pal->palette[idx], 3);
    return 1;
}

/* _read_indices (LSB-first). Returns the new position. */
static size_t read_indices(frame_t *f, size_t start, int num_values, int bits)
{
    if (bits == 0) {
        memset(f->values, 0, sizeof(uint32_t) * (size_t)num_values);
        return start;
    }
    size_t pos = start;
    int bit = 0;
    for (int n = 0; n < num_values; n++) {
        uint32_t v = 0;
        for (int i = 0; i < bits; i++) {
            int b = (pos < f->pixel_len) ? ((f->pixel[pos] >> bit) & 1) : 0;
            v |= (uint32_t)b << i;
            bit++;
            if (bit == 8) {
                bit = 0;
                pos++;
            }
        }
        f->values[n] = v;
    }
    if (bit != 0)
        pos++;
    return pos;
}

/* Build `selected`/`mapping` from an N-bit mask: entries are i (root level, parent_map ==
 * NULL) or parent_map[i] for set bits with i < parent_len. Returns count. */
static int read_mask(frame_t *f, size_t ptr, int N, const int *parent_map, int parent_len,
                     int *dst)
{
    int n = 0;
    for (int i = 0; i < N; i++) {
        if ((f->pixel[ptr + (size_t)(i >> 3)] >> (i & 7)) & 1) {
            if (!parent_map)
                dst[n++] = i;
            else if (i < parent_len)
                dst[n++] = parent_map[i];
        }
    }
    return n;
}

#define FAIL(f)            \
    do {                   \
        (f)->failed = 1;   \
        return 0;          \
    } while (0)

/* Common node header: returns ctrl, sets *N and *ptr. Requires offset+1 < pixel_len. */
static int node_header(frame_t *f, size_t offset, int *N, size_t *ptr)
{
    if (offset + 1 >= f->pixel_len)
        return -1;
    int ctrl = f->pixel[offset];
    if (ctrl == 0) {
        *ptr = offset + 1;
        *N = 0;
    } else {
        *N = f->pixel[offset + 1] ? f->pixel[offset + 1] : 0x100;
        *ptr = offset + 2;
    }
    return ctrl;
}

static size_t decode_fix_8(frame_t *f, size_t offset, int xq, int yq, const int *parent_map,
                           int parent_len);

static size_t decode_fix_16(frame_t *f, size_t offset, int xq, int yq, const int *parent_map,
                            int parent_len)
{
    int x0 = xq * 16, y0 = yq * 16, N;
    size_t ptr;
    int ctrl = node_header(f, offset, &N, &ptr);
    if (ctrl < 0)
        FAIL(f);
    int sel[256], nsel = 0;
    int w = f->width;
    if (ctrl == 2 || (ctrl != 0)) {
        size_t mask_bytes = (size_t)(N + 7) / 8;
        if (ptr + mask_bytes > f->pixel_len)
            FAIL(f);
        nsel = read_mask(f, ptr, N, parent_map, parent_len, sel);
        ptr += mask_bytes;
        if (nsel == 0) {
            sel[0] = 0;
            nsel = 1;
        }
    }
    if (ctrl == 2 || ctrl == 0) {
        const int *map = ctrl == 2 ? sel : parent_map;
        int map_len = ctrl == 2 ? nsel : parent_len;
        int bpp = ctrl == 2 ? bits_from_count(nsel) : bits_from_count(parent_len ? parent_len : 1);
        size_t ptr2 = read_indices(f, ptr, 256, bpp);
        int it = 0;
        for (int row_block = 0; row_block < 2; row_block++)
            for (int band = 0; band < 2; band++) {
                int x_band = x0 + band * 8;
                for (int row = 0; row < 8; row++) {
                    size_t base = (size_t)(y0 + row_block * 8 + row) * (size_t)w + (size_t)x_band;
                    for (int col = 0; col < 8; col++) {
                        int idx = (int)f->values[it++];
                        int pal_index = (idx >= 0 && idx < map_len) ? map[idx] : 0;
                        if (!paint(f, base + (size_t)col, pal_index))
                            FAIL(f);
                    }
                }
            }
        return ptr2 - offset;
    }
    size_t consumed = 0;
    for (int k = 0; k < 4; k++) {
        consumed += decode_fix_8(f, ptr + consumed, xq * 2 + (k & 1), yq * 2 + (k >> 1), sel, nsel);
        if (f->failed)
            return 0;
    }
    return 2 + (size_t)(N + 7) / 8 + consumed;
}

static size_t decode_fix_8(frame_t *f, size_t offset, int xq, int yq, const int *parent_map,
                           int parent_len)
{
    int x0 = xq * 8, y0 = yq * 8;
    if (offset >= f->pixel_len)
        FAIL(f);
    int first = f->pixel[offset];
    int w = f->width;
    int sel[128], nsel = 0;
    const int *map;
    int map_len, bpp;
    size_t ptr;
    if (first & 0x80) {
        int N = first & 0x7F;
        ptr = offset + 1;
        size_t mask_bytes = (size_t)(N + 7) / 8;
        if (ptr + mask_bytes > f->pixel_len)
            FAIL(f);
        nsel = read_mask(f, ptr, N, parent_map, parent_len, sel);
        ptr += mask_bytes;
        if (nsel == 0) {
            sel[0] = 0;
            nsel = 1;
        }
        map = sel;
        map_len = nsel;
        bpp = bits_from_count(nsel);
    } else {
        bpp = bits_from_count(parent_len);
        ptr = offset + 1;
        map = parent_map;
        map_len = parent_len;
    }
    size_t ptr2 = read_indices(f, ptr, 64, bpp);
    int it = 0;
    for (int row = 0; row < 8; row++) {
        size_t base = (size_t)(y0 + row) * (size_t)w + (size_t)x0;
        for (int col = 0; col < 8; col++) {
            int idx = (int)f->values[it++];
            int pal_index = (idx >= 0 && idx < map_len) ? map[idx] : 0;
            if (!paint(f, base + (size_t)col, pal_index))
                FAIL(f);
        }
    }
    return ptr2 - offset;
}

static size_t decode_fix_32(frame_t *f, size_t offset, int xq, int yq, const int *parent_map,
                            int parent_len)
{
    int x0 = xq * 32, y0 = yq * 32, N;
    size_t ptr;
    int ctrl = node_header(f, offset, &N, &ptr);
    if (ctrl < 0)
        FAIL(f);
    int sel[256], nsel = 0;
    int w = f->width;
    if (ctrl != 0) {
        size_t mask_bytes = (size_t)(N + 7) / 8;
        if (ptr + mask_bytes > f->pixel_len)
            FAIL(f);
        nsel = read_mask(f, ptr, N, parent_map, parent_len, sel);
        ptr += mask_bytes;
        if (nsel == 0) {
            sel[0] = 0;
            nsel = 1;
        }
    }
    if (ctrl == 2 || ctrl == 0) {
        const int *map = ctrl == 2 ? sel : parent_map;
        int map_len = ctrl == 2 ? nsel : parent_len;
        int bpp = ctrl == 2 ? bits_from_count(nsel) : bits_from_count(parent_len ? parent_len : 1);
        size_t ptr2 = read_indices(f, ptr, 1024, bpp);
        int it = 0;
        for (int br = 0; br < 4; br++)
            for (int bc = 0; bc < 4; bc++)
                for (int row = 0; row < 8; row++) {
                    size_t base = (size_t)(y0 + br * 8 + row) * (size_t)w + (size_t)(x0 + bc * 8);
                    for (int col = 0; col < 8; col++) {
                        int idx = (int)f->values[it++];
                        int pal_index = (idx >= 0 && idx < map_len) ? map[idx] : 0;
                        if (!paint(f, base + (size_t)col, pal_index))
                            FAIL(f);
                    }
                }
        return ptr2 - offset;
    }
    size_t consumed = 0;
    for (int k = 0; k < 4; k++) {
        consumed += decode_fix_16(f, ptr + consumed, xq * 2 + (k & 1), yq * 2 + (k >> 1), sel, nsel);
        if (f->failed)
            return 0;
    }
    return 2 + (size_t)(N + 7) / 8 + consumed;
}

static size_t decode_fix_64(frame_t *f, size_t offset, int xq, int yq)
{
    int x0 = xq * 64, y0 = yq * 64, N;
    size_t ptr;
    int ctrl = node_header(f, offset, &N, &ptr);
    if (ctrl < 0)
        FAIL(f);
    int sel[256], nsel = 0;
    int w = f->width;
    if (ctrl != 0) {
        size_t mask_bytes = (size_t)(N + 7) / 8;
        if (ptr + mask_bytes > f->pixel_len)
            FAIL(f);
        nsel = read_mask(f, ptr, N, NULL, 0, sel);
        ptr += mask_bytes;
        /* NB: at the root level an empty selection is NOT replaced by [0]. */
    }
    if (ctrl == 2) {
        int bpp = bits_from_count(nsel);
        size_t ptr2 = read_indices(f, ptr, 4096, bpp);
        int it = 0;
        for (int br = 0; br < 8; br++)
            for (int bc = 0; bc < 8; bc++)
                for (int row = 0; row < 8; row++) {
                    size_t base = (size_t)(y0 + br * 8 + row) * (size_t)w + (size_t)(x0 + bc * 8);
                    for (int col = 0; col < 8; col++) {
                        int idx = (int)f->values[it++];
                        if (!(idx >= 0 && idx < nsel))
                            idx = 0;
                        if (nsel == 0)
                            FAIL(f); /* selected[0] on an empty list -> IndexError */
                        if (!paint(f, base + (size_t)col, sel[idx]))
                            FAIL(f);
                    }
                }
        return ptr2 - offset;
    }
    if (ctrl == 0) {
        int bpp = f->base_bpp;
        size_t ptr2 = read_indices(f, ptr, 4096, bpp);
        int it = 0;
        for (int br = 0; br < 8; br++)
            for (int bc = 0; bc < 8; bc++)
                for (int row = 0; row < 8; row++) {
                    size_t base = (size_t)(y0 + br * 8 + row) * (size_t)w + (size_t)(x0 + bc * 8);
                    for (int col = 0; col < 8; col++) {
                        int idx = (int)f->values[it++];
                        int pal_index = (idx >= 0 && idx < f->pal->palette_len) ? idx : 0;
                        if (!paint(f, base + (size_t)col, pal_index))
                            FAIL(f);
                    }
                }
        return ptr2 - offset;
    }
    size_t consumed = 0;
    for (int k = 0; k < 4; k++) {
        consumed += decode_fix_32(f, ptr + consumed, xq * 2 + (k & 1), yq * 2 + (k >> 1), sel, nsel);
        if (f->failed)
            return 0;
    }
    return 2 + (size_t)(N + 7) / 8 + consumed;
}

/* Decode one 0xAA frame with the shared palette state. On "exception" returns
 * SERVOOM_ERR_CORRUPT and leaves `shared` untouched (Python only persists the palette
 * after a successful decode). */
static servoom_status decode_hier_frame(const uint8_t *frame_data, size_t frame_len, int width,
                                        int height, palette_t *shared, uint8_t *out_rgb,
                                        uint32_t *scratch)
{
    if (frame_len < 8 || frame_data[0] != 0xAA)
        return SERVOOM_ERR_CORRUPT;
    int encrypt_type = frame_data[5] & 0x7F;
    int palette_size = frame_data[6] | (frame_data[7] << 8);
    palette_t pal = {NULL, 0, 0};
    servoom_status st;
    if (encrypt_type == 0x13) {
        for (int i = 0; i < shared->palette_len; i++)
            if ((st = palette_push(&pal, shared->palette[i][0], shared->palette[i][1],
                                   shared->palette[i][2])) != SERVOOM_OK)
                goto oom;
    }
    for (int i = 0; i < palette_size; i++) {
        size_t off = 8 + (size_t)i * 3;
        if (off + 2 >= frame_len) {
            free(pal.palette);
            return SERVOOM_ERR_CORRUPT; /* 'Palette OOB' */
        }
        if ((st = palette_push(&pal, frame_data[off], frame_data[off + 1], frame_data[off + 2])) !=
            SERVOOM_OK)
            goto oom;
    }
    size_t pixel_off = 8 + (size_t)palette_size * 3;
    frame_t f;
    memset(&f, 0, sizeof(f));
    f.pixel = frame_data + (pixel_off < frame_len ? pixel_off : frame_len);
    f.pixel_len = pixel_off < frame_len ? frame_len - pixel_off : 0;
    f.pal = &pal;
    f.base_bpp = bits_from_count(pal.palette_len);
    f.width = width;
    f.height = height;
    f.out = out_rgb;
    f.out_px = (size_t)width * height;
    f.values = scratch;
    memset(out_rgb, 0, f.out_px * 3);

    size_t off = decode_fix_64(&f, 0, 0, 0);
    if (!f.failed && width == 128 && height == 128) {
        off += decode_fix_64(&f, off, 1, 0);
        if (!f.failed)
            off += decode_fix_64(&f, off, 0, 1);
        if (!f.failed)
            off += decode_fix_64(&f, off, 1, 1);
    }
    if (f.failed) {
        free(pal.palette);
        return SERVOOM_ERR_CORRUPT;
    }
    /* success: persist the palette */
    free(shared->palette);
    *shared = pal;
    return SERVOOM_OK;
oom:
    free(pal.palette);
    return SERVOOM_ERR_NOMEM;
}

/* ------------------------------------------------------------------------- */
/* Container                                                                 */
/* ------------------------------------------------------------------------- */
typedef struct {
    uint8_t *data; /* frames, each frame_size */
    int n, cap;
    size_t frame_size;
} framelist;

static servoom_status fl_push(framelist *fl, const uint8_t *frame)
{
    if (fl->n == fl->cap) {
        int ncap = fl->cap ? fl->cap * 2 : 16;
        uint8_t *p = (uint8_t *)realloc(fl->data, (size_t)ncap * fl->frame_size + 1);
        if (!p)
            return SERVOOM_ERR_NOMEM;
        fl->data = p;
        fl->cap = ncap;
    }
    memcpy(fl->data + (size_t)fl->n * fl->frame_size, frame, fl->frame_size);
    fl->n++;
    return SERVOOM_OK;
}

/* "duplicate previous frame, else blank" */
static servoom_status fl_push_fallback(framelist *fl)
{
    if (fl->n > 0)
        return fl_push(fl, fl->data + (size_t)(fl->n - 1) * fl->frame_size);
    uint8_t *blank = (uint8_t *)calloc(fl->frame_size ? fl->frame_size : 1, 1);
    if (!blank)
        return SERVOOM_ERR_NOMEM;
    servoom_status st = fl_push(fl, blank);
    free(blank);
    return st;
}

servoom_status sv_decode_fmt26_hier(const uint8_t *hdr, const uint8_t *body, size_t body_len,
                                    servoom_pixel_bean **out)
{
    *out = NULL;
    int total_declared = hdr[0];
    int speed = sv_be16(hdr + 1);
    int row_count = hdr[3], column_count = hdr[4];
    int width = column_count * 16, height = row_count * 16;
    size_t frame_size = (size_t)width * height * 3;

    /* Detect 0x0C frames by probing the first record. */
    int uses_0x0c = 0;
    if (body_len >= 10 && body[4] != 0xAA) {
        uint32_t first_size = sv_be32(body);
        if (first_size > 0 && first_size < body_len && body[9] == 0x0C)
            uses_0x0c = 1;
    }

    framelist fl = {NULL, 0, 0, frame_size};
    servoom_status st = SERVOOM_OK;
    uint8_t *tmp = (uint8_t *)malloc(frame_size > 12288 ? frame_size : 12288);
    uint8_t *scratch_frame = (uint8_t *)malloc(frame_size ? frame_size : 1);
    uint32_t *scratch = (uint32_t *)malloc(sizeof(uint32_t) * 4096);
    palette_t shared = {NULL, 0, 0};
    if (!tmp || !scratch_frame || !scratch) {
        st = SERVOOM_ERR_NOMEM;
        goto done;
    }

    if (uses_0x0c) {
        size_t pos = 0;
        for (int fi = 0; fi < total_declared; fi++) {
            if (body_len - pos < 4)
                break;
            uint32_t size = sv_be32(body + pos);
            pos += 4;
            if (body_len - pos < size)
                break;
            servoom_status fst = sv_decode_0x0c_frame(body + pos, size, 4096, tmp);
            if (fst == SERVOOM_ERR_NOMEM) {
                st = fst;
                goto done;
            }
            if (fst != SERVOOM_OK) {
                if ((st = fl_push_fallback(&fl)) != SERVOOM_OK)
                    goto done;
                break;
            }
            sv_frame_from_rgb(tmp, 12288, frame_size, scratch_frame);
            if ((st = fl_push(&fl, scratch_frame)) != SERVOOM_OK)
                goto done;
            pos += size;
        }
    } else {
        size_t pos = 0;
        int have_payload_len = 0;
        uint32_t payload_len = 0;
        for (int fi = 0; fi < total_declared; fi++) {
            if (pos >= body_len)
                break;
            size_t idx = pos + 4;
            if (idx >= body_len)
                break;
            int raised = 0;
            if (body[idx] != 0xAA) {
                raised = 1; /* ValueError: expected 0xAA */
            } else {
                if (idx + 2 >= body_len)
                    break;
                payload_len = body[idx + 1] | ((uint32_t)body[idx + 2] << 8);
                have_payload_len = 1;
                size_t avail = body_len - idx;
                size_t flen = payload_len < avail ? payload_len : avail;
                const uint8_t *frame_data = body + idx;
                if (flen < 8) {
                    raised = 1; /* 'Truncated frame header' */
                } else {
                    int encrypt_type = frame_data[5] & 0x7F;
                    if (encrypt_type == 0x11) {
                        if (flen < 8 + frame_size) {
                            raised = 1; /* 'Truncated raw RGB payload' */
                        } else {
                            if ((st = fl_push(&fl, frame_data + 8)) != SERVOOM_OK)
                                goto done;
                            shared.palette_len = 0; /* shared_palette = [] */
                        }
                    } else {
                        servoom_status fst = decode_hier_frame(frame_data, flen, width, height,
                                                               &shared, scratch_frame, scratch);
                        if (fst == SERVOOM_ERR_NOMEM) {
                            st = fst;
                            goto done;
                        }
                        if (fst != SERVOOM_OK) {
                            raised = 1;
                        } else if ((st = fl_push(&fl, scratch_frame)) != SERVOOM_OK) {
                            goto done;
                        }
                    }
                }
            }
            if (raised) {
                if ((st = fl_push_fallback(&fl)) != SERVOOM_OK)
                    goto done;
                if (!have_payload_len)
                    break;
            }
            pos = idx + payload_len;
        }
    }

    {
        servoom_pixel_bean *bean = sv_bean_new(26, fl.n, speed, row_count, column_count);
        if (!bean) {
            st = SERVOOM_ERR_NOMEM;
            goto done;
        }
        if (fl.n)
            memcpy(bean->frames, fl.data, (size_t)fl.n * frame_size);
        *out = bean;
    }
done:
    free(fl.data);
    free(tmp);
    free(scratch_frame);
    free(scratch);
    free(shared.palette);
    return st;
}
