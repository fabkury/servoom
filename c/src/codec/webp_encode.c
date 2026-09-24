#include "codec/webp_encode.h"

#include <stdlib.h>
#include <string.h>
#include <webp/encode.h>
#include <webp/mux.h>

/* Pillow's WebPImagePlugin._save_all defaults for a lossless animation. */
#define SV_WEBP_QUALITY 80.0f
#define SV_WEBP_METHOD 0
#define SV_WEBP_KMIN 9
#define SV_WEBP_KMAX 17

servoom_status sv_webp_encode_anim(const uint8_t *rgb, int width, int height, int num_frames,
                                   int duration_ms, uint8_t **out, size_t *out_len)
{
    *out = NULL;
    *out_len = 0;
    if (!rgb || width <= 0 || height <= 0 || num_frames <= 0 || duration_ms < 0)
        return SERVOOM_ERR_ARG;
    if (width > WEBP_MAX_DIMENSION || height > WEBP_MAX_DIMENSION)
        return SERVOOM_ERR_ARG;

    WebPAnimEncoderOptions opts;
    if (!WebPAnimEncoderOptionsInit(&opts))
        return SERVOOM_ERR_CODEC;
    opts.anim_params.loop_count = 0; /* forever */
    opts.anim_params.bgcolor = 0;
    opts.minimize_size = 0;
    opts.kmin = SV_WEBP_KMIN;
    opts.kmax = SV_WEBP_KMAX;
    opts.allow_mixed = 0;
    opts.verbose = 0;

    WebPConfig cfg;
    if (!WebPConfigInit(&cfg))
        return SERVOOM_ERR_CODEC;
    cfg.lossless = 1;
    cfg.quality = SV_WEBP_QUALITY;
    cfg.method = SV_WEBP_METHOD;
    cfg.alpha_quality = 100;
    cfg.exact = 0;
    if (!WebPValidateConfig(&cfg))
        return SERVOOM_ERR_CODEC;

    WebPAnimEncoder *enc = WebPAnimEncoderNew(width, height, &opts);
    if (!enc)
        return SERVOOM_ERR_NOMEM;

    servoom_status st = SERVOOM_OK;
    size_t frame_bytes = (size_t)width * height * 3;
    int timestamp = 0;
    for (int f = 0; f < num_frames && st == SERVOOM_OK; f++) {
        WebPPicture pic;
        if (!WebPPictureInit(&pic)) {
            st = SERVOOM_ERR_CODEC;
            break;
        }
        pic.width = width;
        pic.height = height;
        pic.use_argb = 1; /* lossless works on ARGB */
        if (!WebPPictureImportRGB(&pic, rgb + (size_t)f * frame_bytes, width * 3))
            st = SERVOOM_ERR_NOMEM;
        else if (!WebPAnimEncoderAdd(enc, &pic, timestamp, &cfg))
            st = SERVOOM_ERR_CODEC;
        WebPPictureFree(&pic);
        timestamp += duration_ms;
    }
    /* Flush: gives the last frame its duration (Pillow does the same with add(None)). */
    if (st == SERVOOM_OK && !WebPAnimEncoderAdd(enc, NULL, timestamp, NULL))
        st = SERVOOM_ERR_CODEC;

    WebPData data;
    WebPDataInit(&data);
    if (st == SERVOOM_OK && !WebPAnimEncoderAssemble(enc, &data))
        st = SERVOOM_ERR_CODEC;
    WebPAnimEncoderDelete(enc);
    if (st != SERVOOM_OK) {
        WebPDataClear(&data);
        return st;
    }
    uint8_t *copy = (uint8_t *)malloc(data.size ? data.size : 1);
    if (!copy) {
        WebPDataClear(&data);
        return SERVOOM_ERR_NOMEM;
    }
    memcpy(copy, data.bytes, data.size);
    *out = copy;
    *out_len = data.size;
    WebPDataClear(&data);
    return SERVOOM_OK;
}
