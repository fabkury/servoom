/* Layer-file decoder (formats 0x27 / 0x28). Python LayerFileDecoder / LayerBean. */
#include "servoom/layer_file.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "codec/webp_anim.h"
#include "codec/zstd_util.h"
#include "decoders/decoders.h"
#include "util/bytes.h"
#include "util/fs.h"

#define DESCRIPTOR_SIZE 6

int servoom_format_is_layer(int fmt)
{
    return fmt == SERVOOM_LAYER_FORMAT_RAW_RGB || fmt == SERVOOM_LAYER_FORMAT_WEBP;
}

void servoom_layer_bean_free(servoom_layer_bean *bean)
{
    if (!bean)
        return;
    if (bean->frames) {
        for (int i = 0; i < bean->num_frames; i++)
            free(bean->frames[i].layers);
        free(bean->frames);
    }
    free(bean->bitmaps);
    free(bean);
}

/* _read_zstd_stream: [C BE32][U BE32][zstd frame of C bytes] -> U bytes. */
static servoom_status read_zstd_stream(const uint8_t *data, size_t len, size_t pos,
                                       uint8_t **out, size_t *out_len, size_t *next_pos)
{
    *out = NULL;
    if (pos > len || len - pos < 8)
        return SERVOOM_ERR_CORRUPT; /* unpack on a short slice -> struct.error */
    uint32_t c = sv_be32(data + pos), u = sv_be32(data + pos + 4);
    size_t avail = len - pos - 8;
    size_t clen = c < avail ? c : avail; /* Python slice clamps */
    const uint8_t *comp = data + pos + 8;
    if (clen < 4 || memcmp(comp, SV_ZSTD_MAGIC, 4) != 0)
        return SERVOOM_ERR_CORRUPT; /* 'Expected zstd magic' */
    servoom_status st = sv_zstd_decompress(comp, clen, 0, 0, out, out_len);
    if (st != SERVOOM_OK)
        return st;
    if (*out_len != u) {
        free(*out);
        *out = NULL;
        return SERVOOM_ERR_CORRUPT; /* 'Stream size mismatch' */
    }
    *next_pos = c < avail ? pos + 8 + c : len; /* a declared size past the end clamps */
    return SERVOOM_OK;
}

/* _parse_layer_table */
static servoom_status parse_layer_table(const uint8_t *table, size_t tlen, servoom_layer_bean *bean)
{
    size_t pos = 0;
    int cap = 0;
    while (pos + 2 <= tlen) {
        int num_layers = table[pos], flag = table[pos + 1];
        pos += 2;
        if (bean->num_frames == cap) {
            int ncap = cap ? cap * 2 : 16;
            servoom_layer_frame *nf = (servoom_layer_frame *)realloc(bean->frames, (size_t)ncap * sizeof(*nf));
            if (!nf)
                return SERVOOM_ERR_NOMEM;
            bean->frames = nf;
            cap = ncap;
        }
        servoom_layer_frame *fr = &bean->frames[bean->num_frames];
        memset(fr, 0, sizeof(*fr));
        fr->num_layers = num_layers;
        fr->flag = flag;
        fr->first_layer = bean->total_layers;
        fr->layers = (servoom_layer_meta *)calloc(num_layers ? (size_t)num_layers : 1, sizeof(servoom_layer_meta));
        if (!fr->layers)
            return SERVOOM_ERR_NOMEM;
        bean->num_frames++;
        for (int i = 0; i < num_layers; i++) {
            /* Python slices the descriptor (clamped) and reads desc[0]/desc[1]: a short
             * slice raises IndexError -> decode fails. */
            if (tlen - pos < 2)
                return SERVOOM_ERR_CORRUPT;
            size_t have = tlen - pos < DESCRIPTOR_SIZE ? tlen - pos : DESCRIPTOR_SIZE;
            memcpy(fr->layers[i].descriptor, table + pos, have);
            fr->layers[i].hidden = table[pos] != 0;
            fr->layers[i].opacity = table[pos + 1];
            pos += DESCRIPTOR_SIZE;
        }
        bean->total_layers += num_layers;
    }
    if (pos != tlen)
        return SERVOOM_ERR_CORRUPT; /* 'did not consume stream 0 exactly' */
    return SERVOOM_OK;
}

servoom_status servoom_layer_decode_memory(const uint8_t *data, size_t len, servoom_layer_bean **out)
{
    if (!out)
        return SERVOOM_ERR_ARG;
    *out = NULL;
    if (!data || len == 0 || !servoom_format_is_layer(data[0]))
        return SERVOOM_ERR_FORMAT;
    servoom_layer_bean *bean = (servoom_layer_bean *)calloc(1, sizeof(*bean));
    if (!bean)
        return SERVOOM_ERR_NOMEM;
    bean->format = data[0];

    uint8_t *table = NULL;
    size_t tlen = 0, pos = 0;
    servoom_status st = read_zstd_stream(data, len, 1, &table, &tlen, &pos);
    if (st != SERVOOM_OK)
        goto fail;
    st = parse_layer_table(table, tlen, bean);
    free(table);
    table = NULL;
    if (st != SERVOOM_OK)
        goto fail;
    if (bean->total_layers == 0) {
        st = SERVOOM_ERR_CORRUPT; /* 'declares zero layers' */
        goto fail;
    }

    if (bean->format == SERVOOM_LAYER_FORMAT_RAW_RGB) {
        uint8_t *pix = NULL;
        size_t plen = 0, next = 0;
        st = read_zstd_stream(data, len, pos, &pix, &plen, &next);
        if (st != SERVOOM_OK)
            goto fail;
        double side_f = sqrt((double)plen / (3.0 * bean->total_layers));
        int side = (int)floor(side_f + 0.5); /* round() of a positive number */
        if ((size_t)side * side * 3 * (size_t)bean->total_layers != plen) {
            free(pix);
            st = SERVOOM_ERR_CORRUPT; /* 'non-square canvas?' */
            goto fail;
        }
        bean->width = bean->height = side;
        bean->bitmaps = pix;
    } else {
        int side = -1;
        size_t stride = 0;
        for (int i = 0; i < bean->total_layers; i++) {
            if (pos + 5 > len) {
                st = SERVOOM_ERR_CORRUPT; /* 'Truncated layer record' */
                goto fail;
            }
            uint32_t length = sv_be32(data + pos + 1);
            size_t avail = len - pos - 5;
            size_t wlen = length < avail ? length : avail;
            uint8_t *rgb = NULL;
            int w = 0, h = 0;
            st = sv_webp_decode_rgb(data + pos + 5, wlen, &rgb, &w, &h);
            if (st != SERVOOM_OK)
                goto fail;
            pos += 5 + length;
            if (pos > len)
                pos = len;
            if (side < 0) {
                side = h;
                stride = (size_t)side * side * 3;
                bean->bitmaps = (uint8_t *)malloc(stride * (size_t)bean->total_layers);
                if (!bean->bitmaps) {
                    free(rgb);
                    st = SERVOOM_ERR_NOMEM;
                    goto fail;
                }
            }
            if (w != side || h != side) {
                free(rgb);
                st = SERVOOM_ERR_CORRUPT; /* 'expected side x side RGB bitmap' */
                goto fail;
            }
            memcpy(bean->bitmaps + stride * (size_t)i, rgb, stride);
            free(rgb);
        }
        bean->width = bean->height = side;
    }
    *out = bean;
    return SERVOOM_OK;
fail:
    free(table);
    servoom_layer_bean_free(bean);
    return st;
}

servoom_status servoom_layer_decode_file(const char *path, servoom_layer_bean **out)
{
    if (!path || !out)
        return SERVOOM_ERR_ARG;
    *out = NULL;
    uint8_t *data = NULL;
    size_t len = 0;
    servoom_status st = sv_read_file(path, &data, &len);
    if (st != SERVOOM_OK)
        return st;
    st = servoom_layer_decode_memory(data, len, out);
    free(data);
    return st;
}

const uint8_t *servoom_layer_bitmap(const servoom_layer_bean *bean, int frame, int layer)
{
    if (!bean || frame < 0 || frame >= bean->num_frames)
        return NULL;
    const servoom_layer_frame *fr = &bean->frames[frame];
    if (layer < 0 || layer >= fr->num_layers)
        return NULL;
    size_t stride = (size_t)bean->width * bean->height * 3;
    return bean->bitmaps + stride * (size_t)(fr->first_layer + layer);
}

servoom_status servoom_layer_composite_frame(const servoom_layer_bean *bean, int frame, uint8_t *out_rgb)
{
    if (!bean || !out_rgb || frame < 0 || frame >= bean->num_frames)
        return SERVOOM_ERR_ARG;
    size_t npx = (size_t)bean->width * bean->height;
    double *canvas = (double *)calloc(npx ? npx * 3 : 1, sizeof(double));
    if (!canvas)
        return SERVOOM_ERR_NOMEM;
    const servoom_layer_frame *fr = &bean->frames[frame];
    for (int li = 0; li < fr->num_layers; li++) {
        const servoom_layer_meta *m = &fr->layers[li];
        if (m->hidden)
            continue;
        double alpha = m->opacity / 255.0;
        const uint8_t *layer = servoom_layer_bitmap(bean, frame, li);
        for (size_t p = 0; p < npx; p++) {
            const uint8_t *px = layer + p * 3;
            if (px[0] == 0 && px[1] == 0 && px[2] == 0)
                continue; /* black = transparent */
            for (int ch = 0; ch < 3; ch++)
                canvas[p * 3 + ch] = (double)px[ch] * alpha + canvas[p * 3 + ch] * (1.0 - alpha);
        }
    }
    for (size_t i = 0; i < npx * 3; i++) {
        double v = nearbyint(canvas[i]); /* numpy round: half to even */
        if (v < 0)
            v = 0;
        if (v > 255)
            v = 255;
        out_rgb[i] = (uint8_t)v;
    }
    free(canvas);
    return SERVOOM_OK;
}

servoom_status servoom_layer_to_pixel_bean(const servoom_layer_bean *bean, int speed, servoom_pixel_bean **out)
{
    if (!bean || !out)
        return SERVOOM_ERR_ARG;
    *out = NULL;
    servoom_pixel_bean *pb = sv_bean_new(bean->format, bean->num_frames, speed, bean->height / 16, bean->width / 16);
    if (!pb)
        return SERVOOM_ERR_NOMEM;
    /* A canvas that is not a multiple of 16 cannot be expressed in tiles; keep the true
     * size (the Python PixelBean would report column_count*16 too, but composite frames
     * have the layer size). */
    if (pb->width != bean->width || pb->height != bean->height) {
        servoom_pixel_bean_free(pb);
        return SERVOOM_ERR_CORRUPT;
    }
    size_t fs = servoom_pixel_bean_frame_size(pb);
    for (int f = 0; f < bean->num_frames; f++) {
        servoom_status st = servoom_layer_composite_frame(bean, f, pb->frames + fs * (size_t)f);
        if (st != SERVOOM_OK) {
            servoom_pixel_bean_free(pb);
            return st;
        }
    }
    *out = pb;
    return SERVOOM_OK;
}
