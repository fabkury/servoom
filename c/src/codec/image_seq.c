#include "codec/image_seq.h"

#include <stdlib.h>
#include <string.h>

/* Pillow ImagingTransformAffine with NEAREST: src = (int)((dst + 0.5) * scale). */
uint8_t *sv_resize_nearest_rgb(const uint8_t *src, int sw, int sh, int dw, int dh)
{
    if (dw <= 0 || dh <= 0 || sw <= 0 || sh <= 0)
        return NULL;
    uint8_t *dst = (uint8_t *)malloc((size_t)dw * dh * 3);
    if (!dst)
        return NULL;
    double ax = (double)sw / dw, ay = (double)sh / dh;
    for (int y = 0; y < dh; y++) {
        double yy = (y + 0.5) * ay;
        int yin = yy < 0.0 ? -1 : (int)yy;
        for (int x = 0; x < dw; x++) {
            double xx = (x + 0.5) * ax;
            int xin = xx < 0.0 ? -1 : (int)xx;
            uint8_t *o = dst + ((size_t)y * dw + x) * 3;
            if (xin >= 0 && xin < sw && yin >= 0 && yin < sh)
                memcpy(o, src + ((size_t)yin * sw + xin) * 3, 3);
            else
                o[0] = o[1] = o[2] = 0;
        }
    }
    return dst;
}

#define DIV255(a, tmp) ((tmp) = (a) + 128, ((((tmp) >> 8) + (tmp)) >> 8))
static inline uint8_t blend(int mask, int in1, int in2)
{
    unsigned tmp;
    return (uint8_t)DIV255((unsigned)(in1 * (255 - mask) + in2 * mask), tmp);
}

static servoom_status composite(const uint8_t *(*get)(void *, int), void *ctx, int n, int w,
                                int h, int exp_w, int exp_h, uint8_t **out_rgb)
{
    *out_rgb = NULL;
    if (n <= 0 || w <= 0 || h <= 0 || exp_w <= 0 || exp_h <= 0)
        return SERVOOM_ERR_ARG;
    size_t npx = (size_t)w * h;
    uint8_t *composed = (uint8_t *)malloc(npx * 4);
    uint8_t *out = (uint8_t *)malloc((size_t)n * exp_w * exp_h * 3);
    uint8_t *rgb = (uint8_t *)malloc(npx * 3);
    if (!composed || !out || !rgb) {
        free(composed); free(out); free(rgb);
        return SERVOOM_ERR_NOMEM;
    }
    memset(composed, 255, npx * 4); /* base = white, opaque */
    for (int f = 0; f < n; f++) {
        const uint8_t *frame = get(ctx, f);
        for (size_t i = 0; i < npx; i++) {
            const uint8_t *in = frame + i * 4;
            uint8_t *px = composed + i * 4;
            int a = in[3];
            px[0] = blend(a, px[0], in[0]);
            px[1] = blend(a, px[1], in[1]);
            px[2] = blend(a, px[2], in[2]);
            px[3] = blend(a, px[3], a);
            rgb[i * 3] = px[0];
            rgb[i * 3 + 1] = px[1];
            rgb[i * 3 + 2] = px[2];
        }
        uint8_t *dst = out + (size_t)f * exp_w * exp_h * 3;
        if (w == exp_w && h == exp_h) {
            memcpy(dst, rgb, npx * 3);
        } else {
            uint8_t *r = sv_resize_nearest_rgb(rgb, w, h, exp_w, exp_h);
            if (!r) {
                free(composed); free(out); free(rgb);
                return SERVOOM_ERR_NOMEM;
            }
            memcpy(dst, r, (size_t)exp_w * exp_h * 3);
            free(r);
        }
    }
    free(composed);
    free(rgb);
    *out_rgb = out;
    return SERVOOM_OK;
}

typedef struct { uint8_t *const *frames; } seq_ctx;
static const uint8_t *seq_get(void *p, int i) { return ((seq_ctx *)p)->frames[i]; }

servoom_status sv_composite_rgba_sequence(uint8_t *const *frames, int n, int w, int h,
                                          int exp_w, int exp_h, uint8_t **out_rgb)
{
    seq_ctx ctx = {frames};
    return composite(seq_get, &ctx, n, w, h, exp_w, exp_h, out_rgb);
}

typedef struct { const uint8_t *rgba; size_t stride; } contig_ctx;
static const uint8_t *contig_get(void *p, int i)
{
    contig_ctx *c = (contig_ctx *)p;
    return c->rgba + (size_t)i * c->stride;
}

servoom_status sv_composite_rgba_contig(const uint8_t *rgba, int n, int w, int h,
                                        int exp_w, int exp_h, uint8_t **out_rgb)
{
    contig_ctx ctx = {rgba, (size_t)w * h * 4};
    return composite(contig_get, &ctx, n, w, h, exp_w, exp_h, out_rgb);
}
