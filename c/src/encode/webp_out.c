/* Public WebP output for pixel beans. Always compiled; the encoder itself is only linked
 * when SERVOOM_WITH_WEBP_ENCODER is on, otherwise these report SERVOOM_ERR_UNSUPPORTED. */
#include <stdlib.h>

#include "servoom/pixel_bean.h"
#include "util/fs.h"
#if SERVOOM_WITH_WEBP_ENCODER
#include "codec/webp_encode.h"
#endif

int servoom_has_webp_encoder(void)
{
    return SERVOOM_WITH_WEBP_ENCODER ? 1 : 0;
}

servoom_status servoom_pixel_bean_encode_webp(const servoom_pixel_bean *bean, uint8_t **out,
                                              size_t *out_len)
{
    if (!out || !out_len)
        return SERVOOM_ERR_ARG;
    *out = NULL;
    *out_len = 0;
    if (!bean || !bean->frames || bean->total_frames <= 0)
        return SERVOOM_ERR_ARG;
#if SERVOOM_WITH_WEBP_ENCODER
    return sv_webp_encode_anim(bean->frames, bean->width, bean->height, bean->total_frames,
                               bean->speed < 0 ? 0 : bean->speed, out, out_len);
#else
    return SERVOOM_ERR_UNSUPPORTED;
#endif
}

servoom_status servoom_pixel_bean_write_webp(const servoom_pixel_bean *bean, const char *path)
{
    if (!path)
        return SERVOOM_ERR_ARG;
    uint8_t *data = NULL;
    size_t len = 0;
    servoom_status st = servoom_pixel_bean_encode_webp(bean, &data, &len);
    if (st != SERVOOM_OK)
        return st;
    st = sv_write_file(path, data, len);
    free(data);
    return st;
}
