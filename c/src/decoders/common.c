#include "decoders/decoders.h"

#include <stdlib.h>
#include <string.h>

servoom_pixel_bean *sv_bean_new(int format, int total_frames, int speed, int row_count,
                                int column_count)
{
    if (total_frames < 0 || row_count < 0 || column_count < 0)
        return NULL;
    servoom_pixel_bean *b = (servoom_pixel_bean *)calloc(1, sizeof(*b));
    if (!b)
        return NULL;
    b->format = format;
    b->total_frames = total_frames;
    b->speed = speed;
    b->row_count = row_count;
    b->column_count = column_count;
    b->width = column_count * 16;
    b->height = row_count * 16;
    size_t frame_size = (size_t)b->width * b->height * 3;
    size_t total = frame_size * (size_t)total_frames;
    b->frames = (uint8_t *)calloc(total ? total : 1, 1);
    if (!b->frames) {
        free(b);
        return NULL;
    }
    return b;
}

servoom_status sv_compact_frame(const uint8_t *frame_data, size_t len, int row_count,
                                int column_count, uint8_t *out)
{
    int width = column_count * 16, height = row_count * 16;
    size_t frame_size = (size_t)row_count * column_count * 256 * 3;
    if (len < frame_size)
        return SERVOOM_ERR_CORRUPT; /* unpack('BBB', short slice) -> struct.error */
    memset(out, 0, frame_size);
    size_t pos = 0;
    int x = 0, y = 0, grid_x = 0, grid_y = 0;
    while (pos < frame_size) {
        int real_x = x + grid_x * 16, real_y = y + grid_y * 16;
        if (real_x >= width || real_y >= height)
            return SERVOOM_ERR_CORRUPT; /* numpy IndexError */
        uint8_t *o = out + ((size_t)real_y * width + real_x) * 3;
        o[0] = frame_data[pos];
        o[1] = frame_data[pos + 1];
        o[2] = frame_data[pos + 2];
        x++;
        pos += 3;
        size_t px = pos / 3;
        if (px % 16 == 0) {
            x = 0;
            y++;
        }
        if (px % 256 == 0) {
            x = 0;
            y = 0;
            grid_x++;
            if (grid_x == row_count) { /* sic: the Python code wraps on row_count */
                grid_x = 0;
                grid_y++;
            }
        }
    }
    return SERVOOM_OK;
}

void sv_frame_from_rgb(const uint8_t *buf, size_t len, size_t frame_size, uint8_t *out)
{
    size_t n = len < frame_size ? len : frame_size;
    if (n)
        memcpy(out, buf, n);
    if (n < frame_size)
        memset(out + n, 0, frame_size - n);
}

/* Python _get_dot_info, ported literally (Python ints are unbounded, the values stay
 * small enough for 32-bit arithmetic: bits <= 8, pixel_idx <= 0xFFFF). */
static int get_dot_info(const uint8_t *data, size_t len, uint32_t pos, uint32_t pixel_idx,
                        uint32_t bits, int *err)
{
    if (pos >= len)
        return -1;
    uint32_t uVar2 = (bits * pixel_idx) & 7;
    uint32_t uVar4 = (bits * pixel_idx) >> 3; /* (x * 65536) >> 19 */
    uint32_t uVar6;
    if (bits < 9) {
        uint32_t uVar3 = bits + uVar2;
        if (uVar3 < 9) {
            uint32_t idx = pos + uVar4;
            if (idx >= len)
                return -1;
            uVar6 = ((uint32_t)data[idx] << ((8 - uVar3) & 0xFF)) & 0xFF;
            uVar6 >>= ((uVar2 + (8 - uVar3)) & 0xFF);
        } else {
            uint32_t idx1 = pos + uVar4 + 1, idx0 = pos + uVar4;
            if (idx1 >= len || idx0 >= len)
                return -1;
            uVar6 = ((uint32_t)data[idx1] << ((0x10 - uVar3) & 0xFF)) & 0xFF;
            uVar6 >>= ((0x10 - uVar3) & 0xFF);
            uVar6 &= 0xFFFF;
            uVar6 <<= ((8 - uVar2) & 0xFF);
            uVar6 |= (uint32_t)data[idx0] >> uVar2;
        }
    } else {
        *err = 1; /* raise Exception('(2) Unimplemented') */
        return -1;
    }
    return (int)uVar6;
}

servoom_status sv_decode_0x0c_frame(const uint8_t *data, size_t len, int num_pixels,
                                    uint8_t *out_rgb)
{
    /* Solid-colour fast path: AA 0B 00 F4 01 0C 01 00 R G B */
    if (len == 11 && data[0] == 0xAA && data[1] == 0x0B && data[2] == 0x00 && data[3] == 0xF4 &&
        data[4] == 0x01 && data[5] == 0x0C && data[6] == 0x01 && data[7] == 0x00) {
        for (int i = 0; i < num_pixels; i++) {
            out_rgb[i * 3] = data[8];
            out_rgb[i * 3 + 1] = data[9];
            out_rgb[i * 3 + 2] = data[10];
        }
        return SERVOOM_OK;
    }
    if (len < 8)
        return SERVOOM_ERR_CODEC; /* 'Frame data too short' */
    if (data[5] != 0x0C)
        return SERVOOM_ERR_CODEC; /* 'Expected 0x0C encryption' */

    uint32_t uVar13 = data[6];
    uint32_t iVar11 = uVar13 * 3;
    uint32_t bVar9;
    if (uVar13 == 0) {
        bVar9 = 8;
        iVar11 = 768;
    } else {
        bVar9 = 0xFF;
        uint32_t bVar15 = 1;
        for (;;) {
            if (uVar13 & 1) {
                int bVar18 = (bVar9 == 0xFF);
                bVar9 = bVar15;
                if (bVar18)
                    bVar9 = bVar15 - 1;
            }
            uint32_t uVar14 = uVar13 & 0xFFFE;
            bVar15 += 1;
            uVar13 = uVar14 >> 1;
            if (uVar14 == 0)
                break;
        }
    }

    uint32_t pos = (iVar11 + 8) & 0xFFFF;
    for (int pixel_idx = 0; pixel_idx < num_pixels; pixel_idx++) {
        int err = 0;
        int color_index = get_dot_info(data, len, pos, (uint32_t)pixel_idx & 0xFFFF, bVar9, &err);
        if (err)
            return SERVOOM_ERR_CODEC;
        uint8_t *o = out_rgb + (size_t)pixel_idx * 3;
        if (color_index == -1) {
            o[0] = o[1] = o[2] = 0;
        } else {
            size_t color_pos = 8 + (size_t)color_index * 3;
            if (color_pos + 2 < len) {
                o[0] = data[color_pos];
                o[1] = data[color_pos + 1];
                o[2] = data[color_pos + 2];
            } else {
                o[0] = o[1] = o[2] = 0;
            }
        }
    }
    return SERVOOM_OK;
}
