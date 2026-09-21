#include "codec/webp_anim.h"

#include <stdlib.h>
#include <string.h>
#include <webp/decode.h>
#include <webp/demux.h>

void sv_webp_anim_free(sv_webp_anim *anim)
{
    if (!anim)
        return;
    free(anim->rgba);
    memset(anim, 0, sizeof(*anim));
}

servoom_status sv_webp_decode_anim(const uint8_t *data, size_t len, sv_webp_anim *out)
{
    memset(out, 0, sizeof(*out));
    WebPData wd = {data, len};
    WebPAnimDecoderOptions opts;
    if (!WebPAnimDecoderOptionsInit(&opts))
        return SERVOOM_ERR_CODEC;
    opts.color_mode = MODE_RGBA; /* Pillow: non-premultiplied RGBA */
    opts.use_threads = 0;
    WebPAnimDecoder *dec = WebPAnimDecoderNew(&wd, &opts);
    if (!dec)
        return SERVOOM_ERR_CODEC;
    WebPAnimInfo info;
    if (!WebPAnimDecoderGetInfo(dec, &info) || info.canvas_width == 0 || info.canvas_height == 0) {
        WebPAnimDecoderDelete(dec);
        return SERVOOM_ERR_CODEC;
    }
    size_t frame_bytes = (size_t)info.canvas_width * info.canvas_height * 4;
    size_t cap = frame_bytes * (info.frame_count ? info.frame_count : 1);
    uint8_t *rgba = (uint8_t *)malloc(cap);
    if (!rgba) {
        WebPAnimDecoderDelete(dec);
        return SERVOOM_ERR_NOMEM;
    }
    int n = 0;
    while (WebPAnimDecoderHasMoreFrames(dec)) {
        uint8_t *frame = NULL;
        int timestamp = 0;
        if (!WebPAnimDecoderGetNext(dec, &frame, &timestamp))
            break; /* Pillow raises EOFError here; frames so far are kept by the iterator */
        if ((size_t)(n + 1) * frame_bytes > cap) {
            size_t ncap = cap * 2;
            uint8_t *p = (uint8_t *)realloc(rgba, ncap);
            if (!p) {
                free(rgba);
                WebPAnimDecoderDelete(dec);
                return SERVOOM_ERR_NOMEM;
            }
            rgba = p;
            cap = ncap;
        }
        memcpy(rgba + (size_t)n * frame_bytes, frame, frame_bytes);
        n++;
    }
    WebPAnimDecoderDelete(dec);
    /* Pillow raises EOFError from load() when a frame fails to decode, so a partial
     * sequence is a failure there too. */
    if (n == 0 || (uint32_t)n != info.frame_count) {
        free(rgba);
        return SERVOOM_ERR_CODEC;
    }
    out->width = (int)info.canvas_width;
    out->height = (int)info.canvas_height;
    out->num_frames = n;
    out->rgba = rgba;
    return SERVOOM_OK;
}

servoom_status sv_webp_decode_rgb(const uint8_t *data, size_t len, uint8_t **out_rgb,
                                  int *out_width, int *out_height)
{
    *out_rgb = NULL;
    *out_width = *out_height = 0;
    int w = 0, h = 0;
    if (!WebPGetInfo(data, len, &w, &h) || w <= 0 || h <= 0)
        return SERVOOM_ERR_CODEC;
    size_t stride = (size_t)w * 3;
    uint8_t *rgb = (uint8_t *)malloc(stride * (size_t)h);
    if (!rgb)
        return SERVOOM_ERR_NOMEM;
    if (!WebPDecodeRGBInto(data, len, rgb, stride * (size_t)h, (int)stride)) {
        free(rgb);
        return SERVOOM_ERR_CODEC;
    }
    *out_rgb = rgb;
    *out_width = w;
    *out_height = h;
    return SERVOOM_OK;
}
