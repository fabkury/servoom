/* Unit tests: digests, codecs and synthetic container files whose expected output was
 * produced by the Python decoders (see gen_vectors.py / vectors.h). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "servoom/servoom.h"
#include "codec/aes_cbc.h"
#include "codec/lzo1x.h"
#include "codec/image_seq.h"
#include "decoders/decoders.h"
#include "testlib.h"
#include "vectors.h"

static void test_digests(void)
{
    char hex[65];
    servoom_sha256_hex("abc", 3, hex);
    CHECK(strcmp(hex, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") == 0,
          "sha256(abc) = %s", hex);
    servoom_sha256_hex("", 0, hex);
    CHECK(strcmp(hex, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855") == 0,
          "sha256('') = %s", hex);
    /* 1000 'a' spans several blocks */
    char *a = malloc(1000);
    memset(a, 'a', 1000);
    servoom_sha256_hex(a, 1000, hex);
    CHECK(strcmp(hex, "41edece42d63e8d9bf515a9ba6932e1c20cbc9f5a5d134645adb5db1b9737ea3") == 0,
          "sha256(a*1000) = %s", hex);
    free(a);
    char md5[33];
    servoom_md5_hex("", 0, md5);
    CHECK(strcmp(md5, "d41d8cd98f00b204e9800998ecf8427e") == 0, "md5('') = %s", md5);
    servoom_md5_hex("abc", 3, md5);
    CHECK(strcmp(md5, "900150983cd24fb0d6963f7d28e17f72") == 0, "md5(abc) = %s", md5);
    servoom_md5_hex("The quick brown fox jumps over the lazy dog", 43, md5);
    CHECK(strcmp(md5, "9e107d9d372bb6826bd81d3542a419d6") == 0, "md5(fox) = %s", md5);
}

static void lzo_case(const char *name, const unsigned char *comp, size_t comp_len,
                     const unsigned char *raw, size_t raw_len)
{
    uint8_t *out = NULL;
    size_t out_len = 0;
    servoom_status st = sv_lzo1x_decompress(comp, comp_len, 0, &out, &out_len);
    CHECK(st == SERVOOM_OK, "%s: decompress status %s", name, servoom_status_str(st));
    if (st == SERVOOM_OK) {
        CHECK(out_len == raw_len && memcmp(out, raw, raw_len) == 0,
              "%s: output differs (%zu vs %zu bytes)", name, out_len, raw_len);
    }
    free(out);
    /* a size hint is only a hint */
    st = sv_lzo1x_decompress(comp, comp_len, raw_len / 2 + 1, &out, &out_len);
    CHECK(st == SERVOOM_OK && out_len == raw_len, "%s: small hint still full output", name);
    free(out);
    /* truncated input must fail, never crash */
    if (comp_len > 4) {
        st = sv_lzo1x_decompress(comp, comp_len - 3, 0, &out, &out_len);
        CHECK(st == SERVOOM_ERR_CODEC, "%s: truncated input -> codec error, got %s", name,
              servoom_status_str(st));
        free(out);
    }
}

static void test_lzo(void)
{
    lzo_case("ramp", LZO_RAMP_COMP, LZO_RAMP_COMP_LEN, LZO_RAMP_RAW, LZO_RAMP_RAW_LEN);
    lzo_case("repeat", LZO_REPEAT_COMP, LZO_REPEAT_COMP_LEN, LZO_REPEAT_RAW, LZO_REPEAT_RAW_LEN);
    lzo_case("random", LZO_RANDOM_COMP, LZO_RANDOM_COMP_LEN, LZO_RANDOM_RAW, LZO_RANDOM_RAW_LEN);
    lzo_case("short", LZO_SHORT_COMP, LZO_SHORT_COMP_LEN, LZO_SHORT_RAW, LZO_SHORT_RAW_LEN);
    /* garbage */
    uint8_t junk[16] = {0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff, 0x00};
    uint8_t *out = NULL;
    size_t out_len = 0;
    servoom_status st = sv_lzo1x_decompress(junk, sizeof junk, 0, &out, &out_len);
    CHECK(st != SERVOOM_OK || out_len < 100000, "garbage input handled");
    free(out);
}

static void test_aes(void)
{
    uint8_t buf[AES_CIPHER_LEN];
    memcpy(buf, AES_CIPHER, AES_CIPHER_LEN);
    CHECK(sv_aes_divoom_decrypt(buf, AES_CIPHER_LEN) == SERVOOM_OK, "aes decrypt status");
    CHECK(memcmp(buf, AES_PLAIN, AES_PLAIN_LEN) == 0, "aes decrypt output");
    CHECK(sv_aes_divoom_decrypt(buf, 15) == SERVOOM_ERR_CODEC, "aes rejects non-multiple of 16");
}

static void test_compact(void)
{
    /* one 32x32 frame: tiles (0,0),(1,0),(0,1),(1,1) */
    uint8_t tiles[32 * 32 * 3];
    for (int t = 0; t < 4; t++)
        for (int i = 0; i < 256; i++) {
            tiles[(t * 256 + i) * 3] = (uint8_t)t;
            tiles[(t * 256 + i) * 3 + 1] = (uint8_t)(i / 16);
            tiles[(t * 256 + i) * 3 + 2] = (uint8_t)(i % 16);
        }
    uint8_t out[32 * 32 * 3];
    CHECK(sv_compact_frame(tiles, sizeof tiles, 2, 2, out) == SERVOOM_OK, "compact ok");
    /* pixel (x=20, y=5) is tile 1 (gx=1, gy=0), local (4,5) */
    const uint8_t *p = out + (5 * 32 + 20) * 3;
    CHECK(p[0] == 1 && p[1] == 5 && p[2] == 4, "compact tile placement (%d,%d,%d)", p[0], p[1], p[2]);
    p = out + (25 * 32 + 3) * 3; /* tile 2 (gx=0, gy=1), local (3,9) */
    CHECK(p[0] == 2 && p[1] == 9 && p[2] == 3, "compact tile placement 2");
    CHECK(sv_compact_frame(tiles, 100, 2, 2, out) == SERVOOM_ERR_CORRUPT, "compact short input");
    /* non-square: the Python code raises IndexError -> corrupt */
    uint8_t big[16 * 16 * 3 * 8];
    memset(big, 0, sizeof big);
    uint8_t out2[16 * 16 * 3 * 8];
    CHECK(sv_compact_frame(big, sizeof big, 2, 4, out2) == SERVOOM_ERR_CORRUPT, "compact 2x4 fails like Python");
}

static void test_resize(void)
{
    uint8_t src[2 * 2 * 3] = {1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4};
    uint8_t *dst = sv_resize_nearest_rgb(src, 2, 2, 4, 4);
    CHECK(dst && dst[0] == 1 && dst[(0 * 4 + 3) * 3] == 2 && dst[(3 * 4 + 0) * 3] == 3 && dst[(3 * 4 + 3) * 3] == 4,
          "nearest upscale");
    free(dst);
    dst = sv_resize_nearest_rgb(src, 2, 2, 1, 1);
    CHECK(dst && dst[0] == 4, "nearest downscale picks (int)((0.5)*2)=1 -> pixel (1,1)");
    free(dst);
}

static void synthetic(const char *name, const unsigned char *file, size_t len, const char *expect_hash)
{
    servoom_pixel_bean *bean = NULL;
    servoom_status st = servoom_decode_memory(file, len, &bean);
    if (!CHECK(st == SERVOOM_OK, "%s: decode status %s", name, servoom_status_str(st)))
        return;
    char hex[65];
    tl_bean_hash(bean, hex);
    CHECK(strcmp(hex, expect_hash) == 0, "%s: hash %s != python %s", name, hex, expect_hash);
    servoom_pixel_bean_free(bean);
}

static void test_synthetic_formats(void)
{
    synthetic("fmt09", FMT09_FILE, FMT09_FILE_LEN, FMT09_HASH);
    synthetic("fmt17", FMT17_FILE, FMT17_FILE_LEN, FMT17_HASH);
    synthetic("fmt18", FMT18_FILE, FMT18_FILE_LEN, FMT18_HASH);
    synthetic("fmt26-solid", FMT26_SOLID_FILE, FMT26_SOLID_FILE_LEN, FMT26_SOLID_HASH);
    synthetic("fmt31", FMT31_FILE, FMT31_FILE_LEN, FMT31_HASH);
    synthetic("fmt41", FMT41_FILE, FMT41_FILE_LEN, FMT41_HASH);
    synthetic("fmt42", FMT42_FILE, FMT42_FILE_LEN, FMT42_HASH);
    synthetic("fmt43-gif", FMT43_GIF_FILE, FMT43_GIF_FILE_LEN, FMT43_GIF_HASH);
    synthetic("fmt43-webp", FMT43_WEBP_FILE, FMT43_WEBP_FILE_LEN, FMT43_WEBP_HASH);

    /* structural checks on one of them */
    servoom_pixel_bean *bean = NULL;
    CHECK(servoom_decode_memory(FMT42_FILE, FMT42_FILE_LEN, &bean) == SERVOOM_OK, "fmt42 decode");
    if (bean) {
        CHECK(bean->total_frames == 2 && bean->width == 16 && bean->height == 16 && bean->speed == 100,
              "fmt42 header fields");
        const uint8_t *f1 = servoom_pixel_bean_frame(bean, 1);
        CHECK(f1 && f1[0] == 40 && f1[1] == 50 && f1[2] == 60, "fmt42 frame 1 pixels");
        CHECK(servoom_pixel_bean_frame(bean, 2) == NULL, "frame index out of range");
        servoom_pixel_bean_free(bean);
    }

    /* error paths never crash */
    uint8_t empty[1] = {0};
    CHECK(servoom_decode_memory(empty, 0, &bean) == SERVOOM_ERR_FORMAT && bean == NULL, "empty stream");
    uint8_t unknown[8] = {99, 0, 0, 0, 0, 0, 0, 0};
    CHECK(servoom_decode_memory(unknown, 8, &bean) == SERVOOM_ERR_FORMAT, "unknown format");
    static const int formats[] = {9, 17, 18, 26, 31, 41, 42, 43};
    for (size_t i = 0; i < sizeof formats / sizeof formats[0]; i++) {
        for (size_t n = 1; n <= 24; n++) {
            uint8_t buf[24];
            memset(buf, 0, sizeof buf);
            buf[0] = (uint8_t)formats[i];
            servoom_pixel_bean *b = NULL;
            servoom_status st = servoom_decode_memory(buf, n, &b);
            (void)st;
            servoom_pixel_bean_free(b);
        }
    }
    CHECK(1, "truncated headers survive");
}

static void test_layers(void)
{
    servoom_layer_bean *layer = NULL;
    servoom_status st = servoom_layer_decode_memory(LAYER27_FILE, LAYER27_FILE_LEN, &layer);
    if (CHECK(st == SERVOOM_OK, "layer 0x27 decode: %s", servoom_status_str(st))) {
        char c[65], l[65], t[65];
        tl_layer_hashes(layer, c, l, t);
        CHECK(layer->num_frames == LAYER27_FRAMES && layer->total_layers == LAYER27_TOTAL_LAYERS,
              "layer 0x27 structure");
        CHECK(layer->width == 16 && layer->height == 16, "layer 0x27 side");
        CHECK(strcmp(c, LAYER27_HASH) == 0, "layer 0x27 composite hash");
        CHECK(strcmp(l, LAYER27_LAYERS_HASH) == 0, "layer 0x27 bitmap hash");
        CHECK(layer->frames[0].layers[1].hidden == 1 && layer->frames[0].layers[1].opacity == 128,
              "layer 0x27 descriptor fields");
        /* frame 1: blue at opacity 77 over green at 200 where they overlap (pixel 9,9) */
        uint8_t frame[16 * 16 * 3];
        CHECK(servoom_layer_composite_frame(layer, 1, frame) == SERVOOM_OK, "composite ok");
        servoom_pixel_bean *pb = NULL;
        CHECK(servoom_layer_to_pixel_bean(layer, 100, &pb) == SERVOOM_OK && pb->total_frames == 2,
              "layer -> pixel bean");
        servoom_pixel_bean_free(pb);
        servoom_layer_bean_free(layer);
    }
    st = servoom_layer_decode_memory(LAYER28_FILE, LAYER28_FILE_LEN, &layer);
    if (CHECK(st == SERVOOM_OK, "layer 0x28 decode: %s", servoom_status_str(st))) {
        char c[65], l[65], t[65];
        tl_layer_hashes(layer, c, l, t);
        CHECK(strcmp(c, LAYER28_HASH) == 0, "layer 0x28 composite hash");
        CHECK(strcmp(l, LAYER28_LAYERS_HASH) == 0, "layer 0x28 bitmap hash");
        CHECK(strcmp(c, LAYER27_HASH) == 0, "0x27 and 0x28 composite identically");
        servoom_layer_bean_free(layer);
    }
    uint8_t bad[5] = {0x1A, 0, 0, 0, 0};
    CHECK(servoom_layer_decode_memory(bad, 5, &layer) == SERVOOM_ERR_FORMAT, "not a layer file");
    for (size_t n = 1; n < 40 && n < LAYER28_FILE_LEN; n++) {
        servoom_layer_bean *b = NULL;
        servoom_layer_decode_memory(LAYER28_FILE, n, &b);
        servoom_layer_bean_free(b);
    }
    CHECK(1, "truncated layer files survive");
}

int main(void)
{
    test_digests();
    test_lzo();
    test_aes();
    test_compact();
    test_resize();
    test_synthetic_formats();
    test_layers();
    return tl_finish("test_units");
}
