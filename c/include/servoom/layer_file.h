/* Decoded Divoom layer file (container formats 0x27 and 0x28).
 *
 * The layer file (LayerFileId in gallery metadata) is the editable, layered source of an
 * artwork. See python/layer-tools/LAYER_FILE_FORMAT.md for the format write-up. This is a
 * port of servoom.layer_file_decoder.LayerFileDecoder / LayerBean.
 */
#ifndef SERVOOM_LAYER_FILE_H
#define SERVOOM_LAYER_FILE_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"
#include "servoom/pixel_bean.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SERVOOM_LAYER_FORMAT_RAW_RGB 0x27 /* pixels: one zstd stream of raw RGB bitmaps */
#define SERVOOM_LAYER_FORMAT_WEBP    0x28 /* pixels: one lossless WebP record per layer */

typedef struct servoom_layer_meta {
    uint8_t hidden;        /* descriptor byte[0] != 0: excluded from the composite */
    uint8_t opacity;       /* descriptor byte[1], 0..255 */
    uint8_t descriptor[6]; /* the raw 6-byte descriptor */
} servoom_layer_meta;

typedef struct servoom_layer_frame {
    int num_layers;
    int flag;                    /* per-frame flag byte (unconfirmed meaning) */
    int first_layer;             /* index of this frame's first bitmap in the bean */
    servoom_layer_meta *layers;  /* num_layers entries, bottom -> top */
} servoom_layer_frame;

typedef struct servoom_layer_bean {
    int format;        /* 0x27 or 0x28 */
    int width, height; /* square canvas */
    int num_frames;
    int total_layers;  /* sum of num_layers over all frames */
    servoom_layer_frame *frames;
    uint8_t *bitmaps;  /* total_layers * width * height * 3 bytes, frame-major, bottom -> top */
} servoom_layer_bean;

servoom_status servoom_layer_decode_file(const char *path, servoom_layer_bean **out);
servoom_status servoom_layer_decode_memory(const uint8_t *data, size_t len,
                                           servoom_layer_bean **out);
void servoom_layer_bean_free(servoom_layer_bean *bean);

/* Raw bitmap of layer `layer` of frame `frame` (width*height*3 bytes); NULL if out of range. */
const uint8_t *servoom_layer_bitmap(const servoom_layer_bean *bean, int frame, int layer);

/* Composite one frame the way the Divoom editor does: black is transparent, layers are
 * painted bottom -> top over black with alpha = opacity/255, hidden layers skipped.
 * `out_rgb` must hold width*height*3 bytes. */
servoom_status servoom_layer_composite_frame(const servoom_layer_bean *bean, int frame,
                                             uint8_t *out_rgb);

/* Composite every frame into a pixel bean (speed = ms per frame; the layer file carries
 * no timing, the Python library defaults to 100). */
servoom_status servoom_layer_to_pixel_bean(const servoom_layer_bean *bean, int speed,
                                           servoom_pixel_bean **out);

int servoom_format_is_layer(int format_byte);

#ifdef __cplusplus
}
#endif
#endif
