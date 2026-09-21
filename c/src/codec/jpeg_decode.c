#include "codec/jpeg_decode.h"

#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <jpeglib.h>

typedef struct {
    struct jpeg_error_mgr pub;
    jmp_buf jump;
} sv_jpeg_err;

static void on_error_exit(j_common_ptr cinfo)
{
    sv_jpeg_err *err = (sv_jpeg_err *)cinfo->err;
    longjmp(err->jump, 1);
}

static void on_output_message(j_common_ptr cinfo)
{
    (void)cinfo; /* stay quiet, like Pillow */
}

servoom_status sv_jpeg_decode_rgb(const uint8_t *data, size_t len, uint8_t **out_rgb,
                                  int *out_width, int *out_height)
{
    struct jpeg_decompress_struct cinfo;
    sv_jpeg_err err;
    uint8_t *rgb = NULL;

    *out_rgb = NULL;
    *out_width = *out_height = 0;

    cinfo.err = jpeg_std_error(&err.pub);
    err.pub.error_exit = on_error_exit;
    err.pub.output_message = on_output_message;
    if (setjmp(err.jump)) {
        jpeg_destroy_decompress(&cinfo);
        free(rgb);
        return SERVOOM_ERR_CODEC;
    }
    jpeg_create_decompress(&cinfo);
    jpeg_mem_src(&cinfo, data, (unsigned long)len);
    if (jpeg_read_header(&cinfo, TRUE) != JPEG_HEADER_OK) {
        jpeg_destroy_decompress(&cinfo);
        return SERVOOM_ERR_CODEC;
    }
    /* Pillow: Image.open(...).convert("RGB"). Grayscale and YCbCr both come out as RGB
     * from libjpeg with identical numbers to Pillow's L/YCbCr->RGB conversion. CMYK
     * JPEGs would need Pillow's inverted-CMYK handling; not seen in Divoom files. */
    if (cinfo.num_components == 4) {
        jpeg_destroy_decompress(&cinfo);
        return SERVOOM_ERR_CODEC;
    }
    cinfo.out_color_space = JCS_RGB;
    cinfo.dct_method = JDCT_ISLOW;
    cinfo.do_fancy_upsampling = TRUE;
    cinfo.do_block_smoothing = TRUE;
    jpeg_start_decompress(&cinfo);
    int w = (int)cinfo.output_width, h = (int)cinfo.output_height;
    if (w <= 0 || h <= 0 || cinfo.output_components != 3) {
        jpeg_destroy_decompress(&cinfo);
        return SERVOOM_ERR_CODEC;
    }
    size_t stride = (size_t)w * 3;
    rgb = (uint8_t *)malloc(stride * (size_t)h);
    if (!rgb) {
        jpeg_destroy_decompress(&cinfo);
        return SERVOOM_ERR_NOMEM;
    }
    while (cinfo.output_scanline < cinfo.output_height) {
        JSAMPROW row = rgb + stride * cinfo.output_scanline;
        jpeg_read_scanlines(&cinfo, &row, 1);
    }
    jpeg_finish_decompress(&cinfo);
    jpeg_destroy_decompress(&cinfo);
    *out_rgb = rgb;
    *out_width = w;
    *out_height = h;
    return SERVOOM_OK;
}
