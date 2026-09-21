#include "codec/gif_decode.h"

#include <stdlib.h>
#include <string.h>
#include "util/bytes.h"

/* ------------------------------------------------------------------------- */
/* Byte cursor                                                               */
/* ------------------------------------------------------------------------- */
typedef struct {
    const uint8_t *p;
    size_t len;
    size_t pos;
} cur;

static int cur_need(const cur *c, size_t n) { return c->len - c->pos >= n; }
static int cur_u8(cur *c, uint8_t *v)
{
    if (!cur_need(c, 1))
        return 0;
    *v = c->p[c->pos++];
    return 1;
}
static int cur_u16(cur *c, uint16_t *v)
{
    if (!cur_need(c, 2))
        return 0;
    *v = sv_le16(c->p + c->pos);
    c->pos += 2;
    return 1;
}

/* Read one data sub-block into buf (append). Returns block length, 0 at terminator,
 * -1 on truncation. Pillow's data(): a truncated block returns None (=> stop). */
static int read_subblock(cur *c, sv_buf *buf)
{
    uint8_t n;
    if (!cur_u8(c, &n))
        return -1;
    if (n == 0)
        return 0;
    if (!cur_need(c, n))
        return -1;
    if (buf && sv_buf_append(buf, c->p + c->pos, n) != SERVOOM_OK)
        return -1;
    c->pos += n;
    return n;
}

static void skip_subblocks(cur *c)
{
    while (read_subblock(c, NULL) > 0) {
    }
}

/* ------------------------------------------------------------------------- */
/* Palettes                                                                  */
/* ------------------------------------------------------------------------- */
typedef struct {
    uint8_t rgb[256 * 3]; /* full 256 entries; unreferenced entries = grey ramp (Pillow) */
    int entries;          /* entries actually present in the file (2..256) */
    int present;          /* 0 => "mode L": identity ramp */
} palette;

static void palette_identity(palette *pal)
{
    for (int i = 0; i < 256; i++)
        pal->rgb[i * 3] = pal->rgb[i * 3 + 1] = pal->rgb[i * 3 + 2] = (uint8_t)i;
    pal->entries = 256;
    pal->present = 0;
}

/* Pillow's _is_palette_needed: false when entry i == (i, i, i) for every i. */
static int palette_needed(const uint8_t *p, int entries)
{
    for (int i = 0; i < entries; i++)
        if (!(p[i * 3] == i && p[i * 3 + 1] == i && p[i * 3 + 2] == i))
            return 1;
    return 0;
}

static void palette_load(palette *pal, const uint8_t *p, int entries)
{
    palette_identity(pal);
    if (!palette_needed(p, entries))
        return; /* Pillow drops it and uses mode L, which is the identity ramp */
    memcpy(pal->rgb, p, (size_t)entries * 3);
    pal->entries = entries;
    pal->present = 1;
}

/* Pillow's _rgb(color) helper used for disposal fills. */
static void palette_rgb_for_fill(const palette *pal, int color, uint8_t out[3])
{
    if (!pal->present) {
        out[0] = out[1] = out[2] = (uint8_t)color;
        return;
    }
    if (color * 3 + 3 > pal->entries * 3)
        color = 0;
    memcpy(out, pal->rgb + color * 3, 3);
}

/* ------------------------------------------------------------------------- */
/* LZW                                                                       */
/* ------------------------------------------------------------------------- */
/* Decode LZW image data into `idx` (rect w*h, row-major, interlace handled). Returns
 * SERVOOM_OK when every pixel of the rect was produced, SERVOOM_ERR_CORRUPT otherwise
 * (Pillow raises "image file is truncated" / "broken data stream"). */
static servoom_status lzw_decode(const uint8_t *data, size_t len, int min_code_size,
                                 int w, int h, int interlace, uint8_t *idx)
{
    if (min_code_size < 1 || min_code_size > 11)
        return SERVOOM_ERR_CORRUPT;
    size_t npix = (size_t)w * h, out_n = 0;
    if (npix == 0)
        return SERVOOM_OK;

    /* Row mapping for interlaced images. */
    int *row_of = (int *)malloc(sizeof(int) * (size_t)(h > 0 ? h : 1));
    if (!row_of)
        return SERVOOM_ERR_NOMEM;
    if (interlace) {
        int r = 0;
        static const int start[4] = {0, 4, 2, 1}, step[4] = {8, 8, 4, 2};
        for (int pass = 0; pass < 4; pass++)
            for (int y = start[pass]; y < h; y += step[pass])
                row_of[r++] = y;
    } else {
        for (int y = 0; y < h; y++)
            row_of[y] = y;
    }

    uint16_t *prefix = (uint16_t *)malloc(4096 * sizeof(uint16_t));
    uint8_t *suffix = (uint8_t *)malloc(4096);
    uint8_t *stack = (uint8_t *)malloc(4097);
    if (!prefix || !suffix || !stack) {
        free(row_of); free(prefix); free(suffix); free(stack);
        return SERVOOM_ERR_NOMEM;
    }

    int clear = 1 << min_code_size, eoi = clear + 1;
    int code_size = min_code_size + 1, next = clear + 2, prev = -1;
    int code_mask = (1 << code_size) - 1;
    uint32_t bitbuf = 0;
    int bitcnt = 0;
    size_t ip = 0;
    servoom_status st = SERVOOM_ERR_CORRUPT;
    int first = 0;

    for (int i = 0; i < clear; i++) {
        prefix[i] = 0xFFFF;
        suffix[i] = (uint8_t)i;
    }

    while (out_n < npix) {
        while (bitcnt < code_size) {
            if (ip >= len)
                goto done; /* ran out of data before the rect was full */
            bitbuf |= (uint32_t)data[ip++] << bitcnt;
            bitcnt += 8;
        }
        int code = (int)(bitbuf & (uint32_t)code_mask);
        bitbuf >>= code_size;
        bitcnt -= code_size;

        if (code == clear) {
            code_size = min_code_size + 1;
            code_mask = (1 << code_size) - 1;
            next = clear + 2;
            prev = -1;
            continue;
        }
        if (code == eoi)
            goto done;
        if (prev == -1) {
            if (code >= clear)
                goto done; /* invalid first code */
            first = code;
            size_t o = out_n;
            idx[(size_t)row_of[o / (size_t)w] * (size_t)w + (o % (size_t)w)] = (uint8_t)code;
            out_n++;
            prev = code;
            continue;
        }
        int sp = 0, cur_code = code;
        if (code >= next) {
            if (code != next)
                goto done; /* corrupt */
            stack[sp++] = (uint8_t)first;
            cur_code = prev;
        }
        while (cur_code >= clear) {
            stack[sp++] = suffix[cur_code];
            cur_code = prefix[cur_code];
            if (sp > 4096)
                goto done;
        }
        stack[sp++] = suffix[cur_code];
        first = suffix[cur_code];
        if (next < 4096) {
            prefix[next] = (uint16_t)prev;
            suffix[next] = (uint8_t)first;
            next++;
            if (next > code_mask && code_size < 12) {
                code_size++;
                code_mask = (1 << code_size) - 1;
            }
        }
        prev = code;
        while (sp > 0 && out_n < npix) {
            size_t o = out_n;
            idx[(size_t)row_of[o / (size_t)w] * (size_t)w + (o % (size_t)w)] = stack[--sp];
            out_n++;
        }
    }
done:
    st = (out_n == npix) ? SERVOOM_OK : SERVOOM_ERR_CORRUPT;
    free(row_of); free(prefix); free(suffix); free(stack);
    return st;
}

/* ------------------------------------------------------------------------- */
/* Canvas (Pillow's self.im across frames)                                   */
/* ------------------------------------------------------------------------- */
typedef struct {
    int w, h;
    uint8_t *rgba; /* w*h*4 */
} canvas;

static servoom_status canvas_alloc(canvas *c, int w, int h)
{
    c->w = w;
    c->h = h;
    c->rgba = (uint8_t *)calloc((size_t)w * h * 4, 1);
    return c->rgba ? SERVOOM_OK : SERVOOM_ERR_NOMEM;
}

/* Grow to (w,h); new area transparent black (Pillow fills with zeros). */
static servoom_status canvas_grow(canvas *c, int w, int h)
{
    if (w <= c->w && h <= c->h)
        return SERVOOM_OK;
    int nw = w > c->w ? w : c->w, nh = h > c->h ? h : c->h;
    uint8_t *n = (uint8_t *)calloc((size_t)nw * nh * 4, 1);
    if (!n)
        return SERVOOM_ERR_NOMEM;
    for (int y = 0; y < c->h; y++)
        memcpy(n + (size_t)y * nw * 4, c->rgba + (size_t)y * c->w * 4, (size_t)c->w * 4);
    free(c->rgba);
    c->rgba = n;
    c->w = nw;
    c->h = nh;
    return SERVOOM_OK;
}

/* Pillow's Paste.c blend: DIV255(in1*(255-mask) + in2*mask). */
#define DIV255(a, tmp) ((tmp) = (a) + 128, ((((tmp) >> 8) + (tmp)) >> 8))
static inline uint8_t blend(int mask, int in1, int in2)
{
    unsigned tmp;
    return (uint8_t)DIV255((unsigned)(in1 * (255 - mask) + in2 * mask), tmp);
}

/* ------------------------------------------------------------------------- */
/* Decoder                                                                   */
/* ------------------------------------------------------------------------- */
typedef struct {
    int x0, y0, x1, y1;
} rect;

static servoom_status push_frame(sv_gif_anim *out, size_t *cap, const canvas *c)
{
    if ((size_t)out->num_frames == *cap) {
        size_t ncap = *cap ? *cap * 2 : 8;
        uint8_t **p = (uint8_t **)realloc(out->frames, ncap * sizeof(uint8_t *));
        if (!p)
            return SERVOOM_ERR_NOMEM;
        out->frames = p;
        *cap = ncap;
    }
    uint8_t *copy = sv_memdup(c->rgba, (size_t)c->w * c->h * 4);
    if (!copy)
        return SERVOOM_ERR_NOMEM;
    out->frames[out->num_frames++] = copy;
    return SERVOOM_OK;
}

void sv_gif_anim_free(sv_gif_anim *anim)
{
    if (!anim)
        return;
    for (int i = 0; i < anim->num_frames; i++)
        free(anim->frames[i]);
    free(anim->frames);
    memset(anim, 0, sizeof(*anim));
}

servoom_status sv_gif_decode(const uint8_t *data, size_t len, sv_gif_anim *out)
{
    memset(out, 0, sizeof(*out));
    cur c = {data, len, 0};
    if (len < 13 || memcmp(data, "GIF8", 4) != 0)
        return SERVOOM_ERR_CORRUPT;
    c.pos = 6;
    uint16_t sw, sh;
    uint8_t flags, background, aspect;
    cur_u16(&c, &sw);
    cur_u16(&c, &sh);
    cur_u8(&c, &flags);
    cur_u8(&c, &background);
    cur_u8(&c, &aspect);
    (void)aspect;

    palette global;
    palette_identity(&global);
    if (flags & 0x80) {
        int entries = 1 << ((flags & 7) + 1);
        if (!cur_need(&c, (size_t)entries * 3))
            return SERVOOM_ERR_CORRUPT;
        palette_load(&global, c.p + c.pos, entries);
        c.pos += (size_t)entries * 3;
    }

    /* Pillow: self.info["background"] only if there is a global palette. */
    int have_background = (flags & 0x80) ? 1 : 0;

    canvas cv = {0, 0, NULL};
    servoom_status st = SERVOOM_OK;
    size_t cap = 0;
    uint8_t *idx = NULL;
    sv_buf lzw;
    sv_buf_init(&lzw);

    /* Persistent plugin state. */
    int frame = 0;
    int disposal_method = 0;         /* sticky */
    int mode_p = 1;                  /* frame 0 canvas is "P"; later frames RGB/RGBA */
    int info_transparency = -1;      /* self.info["transparency"], frame 0 only */
    int canvas_is_rgba = 0;          /* after conversion: RGBA (had transparency) or RGB */
    rect dispose_extent = {0, 0, 0, 0};
    /* self.dispose: kind 0 none, 1 fill(colour, alpha), 2 restore(saved pixels) */
    int dispose_kind = 0;
    uint8_t dispose_fill[4] = {0, 0, 0, 0};
    uint8_t *dispose_saved = NULL;
    int dispose_saved_w = 0, dispose_saved_h = 0;
    palette frame_pal;
    /* The P canvas of frame 0 is kept as indices + palette until conversion. */
    uint8_t *pcanvas = NULL;
    palette pcanvas_pal;
    palette_identity(&pcanvas_pal);
    int pcanvas_w = 0, pcanvas_h = 0;

    if ((st = canvas_alloc(&cv, sw, sh)) != SERVOOM_OK)
        goto out;
    out->width = sw;
    out->height = sh;

    for (;;) {
        /* ---- _seek(frame): scan blocks until an image descriptor ------------- */
        int frame_transparency = -1;
        int have_image = 0;
        rect r = {0, 0, 0, 0};
        int interlace = 0;
        int local_present = 0;
        palette local;
        palette_identity(&local);
        uint8_t min_code = 0;
        uint8_t s;
        if (!cur_u8(&c, &s) || s == ';')
            break; /* EOFError: no more images */
        for (;;) {
            if (s == '!') {
                uint8_t label;
                if (!cur_u8(&c, &label))
                    goto no_image;
                sv_buf block;
                sv_buf_init(&block);
                int n = read_subblock(&c, &block);
                if (label == 0xF9 && n > 0) {
                    uint8_t gflags = block.data[0];
                    if ((gflags & 1) && block.len >= 4)
                        frame_transparency = block.data[3];
                    int dispose_bits = (gflags & 0x1C) >> 2;
                    if (dispose_bits)
                        disposal_method = dispose_bits;
                }
                sv_buf_free(&block);
                if (n < 0)
                    goto no_image;
                skip_subblocks(&c);
            } else if (s == ',') {
                uint16_t x0, y0, w, h;
                uint8_t iflags;
                if (!cur_u16(&c, &x0) || !cur_u16(&c, &y0) || !cur_u16(&c, &w) ||
                    !cur_u16(&c, &h) || !cur_u8(&c, &iflags))
                    goto no_image;
                r.x0 = x0; r.y0 = y0; r.x1 = x0 + w; r.y1 = y0 + h;
                interlace = (iflags & 0x40) != 0;
                if (iflags & 0x80) {
                    int entries = 1 << ((iflags & 7) + 1);
                    if (!cur_need(&c, (size_t)entries * 3))
                        goto no_image;
                    if (palette_needed(c.p + c.pos, entries)) {
                        palette_load(&local, c.p + c.pos, entries);
                        local_present = 1;
                    } else {
                        local_present = 2; /* Pillow: palette = False => mode L */
                    }
                    c.pos += (size_t)entries * 3;
                }
                if (!cur_u8(&c, &min_code))
                    goto no_image;
                have_image = 1;
                break;
            } else {
                /* unknown block byte: Pillow reads on (s = b"" -> read next) */
            }
            if (!cur_u8(&c, &s) || s == ';')
                break;
        }
    no_image:
        if (!have_image)
            break; /* EOFError("image not found in GIF frame") ends the iterator */

        /* Canvas may grow. */
        if (r.x1 > cv.w || r.y1 > cv.h) {
            if ((st = canvas_grow(&cv, r.x1, r.y1)) != SERVOOM_OK)
                goto out;
            if (pcanvas) {
                uint8_t *np = (uint8_t *)calloc((size_t)cv.w * cv.h, 1);
                if (!np) { st = SERVOOM_ERR_NOMEM; goto out; }
                for (int y = 0; y < pcanvas_h; y++)
                    memcpy(np + (size_t)y * cv.w, pcanvas + (size_t)y * pcanvas_w, (size_t)pcanvas_w);
                free(pcanvas);
                pcanvas = np;
                pcanvas_w = cv.w;
                pcanvas_h = cv.h;
            }
            out->width = cv.w;
            out->height = cv.h;
        }

        /* Apply the previous frame's disposal (self.dispose) to the current canvas. */
        if (dispose_kind != 0) {
            int dx0 = dispose_extent.x0, dy0 = dispose_extent.y0;
            int dx1 = dispose_extent.x1 < cv.w ? dispose_extent.x1 : cv.w;
            int dy1 = dispose_extent.y1 < cv.h ? dispose_extent.y1 : cv.h;
            for (int y = dy0; y < dy1; y++) {
                for (int x = dx0; x < dx1; x++) {
                    if (mode_p) {
                        /* dispose is a P fill with the index colour */
                        pcanvas[(size_t)y * cv.w + x] = dispose_fill[0];
                    } else if (dispose_kind == 1) {
                        uint8_t *px = cv.rgba + ((size_t)y * cv.w + x) * 4;
                        memcpy(px, dispose_fill, 4);
                    } else {
                        const uint8_t *src = dispose_saved +
                            ((size_t)(y - dispose_extent.y0) * dispose_saved_w + (x - dispose_extent.x0)) * 4;
                        memcpy(cv.rgba + ((size_t)y * cv.w + x) * 4, src, 4);
                    }
                }
            }
        }
        free(dispose_saved);
        dispose_saved = NULL;
        dispose_kind = 0;

        /* self._frame_palette */
        if (local_present == 1)
            frame_pal = local;
        else if (local_present == 2)
            palette_identity(&frame_pal);
        else
            frame_pal = global;

        if (frame == 0) {
            /* mode P (or L); canvas filled with transparent index or 0 */
            pcanvas_w = cv.w;
            pcanvas_h = cv.h;
            pcanvas = (uint8_t *)malloc((size_t)cv.w * cv.h);
            if (!pcanvas) { st = SERVOOM_ERR_NOMEM; goto out; }
            memset(pcanvas, frame_transparency >= 0 ? frame_transparency : 0, (size_t)cv.w * cv.h);
            pcanvas_pal = frame_pal;
        } else if (mode_p) {
            /* First later frame: convert the P canvas to RGBA/RGB (RGB_AFTER_FIRST). */
            canvas_is_rgba = info_transparency >= 0;
            for (size_t i = 0; i < (size_t)cv.w * cv.h; i++) {
                int v = pcanvas[i];
                uint8_t *px = cv.rgba + i * 4;
                memcpy(px, pcanvas_pal.rgb + v * 3, 3);
                px[3] = (canvas_is_rgba && v == info_transparency) ? 0 : 255;
            }
            info_transparency = -1;
            mode_p = 0;
        }

        /* Compute self.dispose for THIS frame (applied before the next one). */
        dispose_extent = r;
        if (disposal_method >= 2) {
            if (disposal_method == 2) {
                int color = frame == 0 ? frame_transparency
                                       : (info_transparency >= 0 ? info_transparency : frame_transparency);
                if (color >= 0) {
                    if (mode_p) {
                        dispose_fill[0] = (uint8_t)color;
                    } else {
                        palette_rgb_for_fill(&frame_pal, color, dispose_fill);
                        dispose_fill[3] = 0;
                    }
                    dispose_kind = 1;
                } else {
                    int bg = have_background ? background : 0;
                    if (mode_p) {
                        dispose_fill[0] = (uint8_t)bg;
                    } else {
                        palette_rgb_for_fill(&frame_pal, bg, dispose_fill);
                        dispose_fill[3] = 255; /* RGB fill: opaque */
                    }
                    dispose_kind = 1;
                }
            } else {
                if (frame > 0) {
                    /* self._im is not None: save the rect of the current canvas */
                    int rw = r.x1 - r.x0, rh = r.y1 - r.y0;
                    dispose_saved = (uint8_t *)malloc((size_t)rw * rh * 4 + 1);
                    if (!dispose_saved) { st = SERVOOM_ERR_NOMEM; goto out; }
                    dispose_saved_w = rw;
                    dispose_saved_h = rh;
                    for (int y = 0; y < rh; y++)
                        memcpy(dispose_saved + (size_t)y * rw * 4,
                               cv.rgba + ((size_t)(r.y0 + y) * cv.w + r.x0) * 4, (size_t)rw * 4);
                    dispose_kind = 2;
                } else if (frame_transparency >= 0) {
                    dispose_fill[0] = (uint8_t)frame_transparency;
                    dispose_kind = 1;
                }
            }
        }
        if (frame_transparency >= 0 && frame == 0)
            info_transparency = frame_transparency;

        /* ---- load(): LZW-decode the rect ----------------------------------- */
        int rw = r.x1 - r.x0, rh = r.y1 - r.y0;
        lzw.len = 0;
        for (;;) {
            int n = read_subblock(&c, &lzw);
            if (n < 0) { st = SERVOOM_ERR_CORRUPT; goto out; } /* truncated file */
            if (n == 0)
                break;
        }
        free(idx);
        idx = (uint8_t *)malloc((size_t)rw * rh + 1);
        if (!idx) { st = SERVOOM_ERR_NOMEM; goto out; }
        memset(idx, frame == 0 ? (frame_transparency >= 0 ? frame_transparency : 0)
                               : (frame_transparency >= 0 ? frame_transparency : 0), (size_t)rw * rh);
        st = lzw_decode(lzw.data, lzw.len, min_code, rw, rh, interlace, idx);
        if (st != SERVOOM_OK)
            goto out; /* Pillow: OSError (truncated / broken) */

        if (frame == 0) {
            for (int y = 0; y < rh; y++)
                memcpy(pcanvas + (size_t)(r.y0 + y) * cv.w + r.x0, idx + (size_t)y * rw, (size_t)rw);
            /* Yielded frame 0: convert("RGBA") of the P image with info["transparency"]. */
            for (size_t i = 0; i < (size_t)cv.w * cv.h; i++) {
                int v = pcanvas[i];
                uint8_t *px = cv.rgba + i * 4;
                memcpy(px, pcanvas_pal.rgb + v * 3, 3);
                px[3] = (info_transparency >= 0 && v == info_transparency) ? 0 : 255;
            }
        } else {
            /* load_end(): paste the decoded rect (RGBA if transparent, else RGB) */
            for (int y = 0; y < rh; y++) {
                for (int x = 0; x < rw; x++) {
                    int v = idx[(size_t)y * rw + x];
                    uint8_t *px = cv.rgba + ((size_t)(r.y0 + y) * cv.w + (r.x0 + x)) * 4;
                    const uint8_t *col = frame_pal.rgb + v * 3;
                    if (frame_transparency >= 0) {
                        int a = (v == frame_transparency) ? 0 : 255;
                        if (canvas_is_rgba) {
                            px[0] = blend(a, px[0], col[0]);
                            px[1] = blend(a, px[1], col[1]);
                            px[2] = blend(a, px[2], col[2]);
                            px[3] = blend(a, px[3], a);
                        } else if (a) {
                            memcpy(px, col, 3);
                            px[3] = 255;
                        }
                    } else {
                        memcpy(px, col, 3);
                        if (canvas_is_rgba) {
                            /* RGB frame pasted on RGBA: Pillow's paste without mask copies
                             * RGB and sets alpha to 255 (ImagingPaste converts via "RGB"
                             * -> RGBA with opaque alpha). */
                            px[3] = 255;
                        } else {
                            px[3] = 255;
                        }
                    }
                }
            }
        }
        if ((st = push_frame(out, &cap, &cv)) != SERVOOM_OK)
            goto out;
        frame++;
        /* Pillow's __offset skip: remaining sub-blocks already consumed. */
    }
    st = out->num_frames ? SERVOOM_OK : SERVOOM_ERR_CORRUPT;

out:
    free(idx);
    free(pcanvas);
    free(dispose_saved);
    free(cv.rgba);
    sv_buf_free(&lzw);
    if (st != SERVOOM_OK)
        sv_gif_anim_free(out);
    return st;
}
