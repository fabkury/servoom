/* Public pixel-bean API: dispatch on the format byte (Python PixelBeanDecoder). */
#include "servoom/pixel_bean.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "decoders/decoders.h"
#include "util/fs.h"

int servoom_format_is_artwork(int fmt)
{
    switch (fmt) {
    case 8: case 9: case 12: case 17: case 18: case 26: case 31: case 41: case 42: case 43:
        return 1;
    default:
        return 0;
    }
}

servoom_status servoom_decode_memory(const uint8_t *data, size_t len, servoom_pixel_bean **out)
{
    if (!out)
        return SERVOOM_ERR_ARG;
    *out = NULL;
    if (!data || len == 0)
        return SERVOOM_ERR_FORMAT; /* 'Empty stream' -> None */
    const uint8_t *body = data + 1;
    size_t blen = len - 1;
    switch (data[0]) {
    case 8:  return sv_decode_fmt08(body, blen, out);
    case 9:  return sv_decode_fmt09(body, blen, out);
    case 12: return sv_decode_fmt12(body, blen, out);
    case 17: return sv_decode_fmt17(body, blen, out);
    case 18: return sv_decode_fmt18(body, blen, out);
    case 26: return sv_decode_fmt26(body, blen, out);
    case 31: return sv_decode_fmt31(body, blen, out);
    case 41: return sv_decode_fmt41(body, blen, out);
    case 42: return sv_decode_fmt42(body, blen, out);
    case 43: return sv_decode_fmt43(body, blen, out);
    default: return SERVOOM_ERR_FORMAT;
    }
}

servoom_status servoom_decode_file(const char *path, servoom_pixel_bean **out)
{
    if (!path || !out)
        return SERVOOM_ERR_ARG;
    *out = NULL;
    uint8_t *data = NULL;
    size_t len = 0;
    servoom_status st = sv_read_file(path, &data, &len);
    if (st != SERVOOM_OK)
        return st;
    st = servoom_decode_memory(data, len, out);
    free(data);
    return st;
}

size_t servoom_pixel_bean_frame_size(const servoom_pixel_bean *bean)
{
    return bean ? (size_t)bean->width * bean->height * 3 : 0;
}

const uint8_t *servoom_pixel_bean_frame(const servoom_pixel_bean *bean, int index)
{
    if (!bean || index < 0 || index >= bean->total_frames)
        return NULL;
    return bean->frames + (size_t)index * servoom_pixel_bean_frame_size(bean);
}

void servoom_pixel_bean_free(servoom_pixel_bean *bean)
{
    if (!bean)
        return;
    free(bean->frames);
    free(bean);
}

servoom_status servoom_pixel_bean_write_ppm(const servoom_pixel_bean *bean, int index,
                                            const char *path)
{
    const uint8_t *frame = servoom_pixel_bean_frame(bean, index);
    if (!frame || !path)
        return SERVOOM_ERR_ARG;
    FILE *fp = fopen(path, "wb");
    if (!fp)
        return SERVOOM_ERR_IO;
    fprintf(fp, "P6\n%d %d\n255\n", bean->width, bean->height);
    size_t n = servoom_pixel_bean_frame_size(bean);
    int ok = fwrite(frame, 1, n, fp) == n;
    fclose(fp);
    return ok ? SERVOOM_OK : SERVOOM_ERR_IO;
}
