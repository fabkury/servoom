#include "testlib.h"

#include "codec/webp_anim.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int tl_failures = 0;
int tl_checks = 0;

int tl_check(int cond, const char *file, int line, const char *fmt, ...)
{
    tl_checks++;
    if (!cond) {
        tl_failures++;
        va_list ap;
        va_start(ap, fmt);
        fprintf(stderr, "FAIL %s:%d: ", file, line);
        vfprintf(stderr, fmt, ap);
        fputc('\n', stderr);
        va_end(ap);
    }
    return cond;
}

int tl_finish(const char *program)
{
    printf("%s: %d checks, %d failure(s)\n", program, tl_checks, tl_failures);
    return tl_failures ? 1 : 0;
}

void tl_bean_hash(const servoom_pixel_bean *bean, char hex[65])
{
    servoom_sha256 ctx;
    uint8_t digest[32];
    servoom_sha256_init(&ctx);
    servoom_sha256_update(&ctx, bean->frames,
                          servoom_pixel_bean_frame_size(bean) * (size_t)bean->total_frames);
    servoom_sha256_final(&ctx, digest);
    servoom_digest_to_hex(digest, 32, hex);
}

void tl_layer_hashes(const servoom_layer_bean *bean, char composite[65], char layers[65],
                     char table[65])
{
    servoom_sha256 c, l, t;
    uint8_t digest[32];
    size_t fs = (size_t)bean->width * bean->height * 3;
    uint8_t *frame = (uint8_t *)malloc(fs ? fs : 1);
    servoom_sha256_init(&c);
    servoom_sha256_init(&l);
    servoom_sha256_init(&t);
    for (int f = 0; f < bean->num_frames; f++) {
        if (servoom_layer_composite_frame(bean, f, frame) == SERVOOM_OK)
            servoom_sha256_update(&c, frame, fs);
        const servoom_layer_frame *fr = &bean->frames[f];
        uint8_t hdr[2] = {(uint8_t)fr->num_layers, (uint8_t)fr->flag};
        servoom_sha256_update(&t, hdr, 2);
        for (int i = 0; i < fr->num_layers; i++) {
            uint8_t m[2] = {fr->layers[i].hidden ? 1 : 0, fr->layers[i].opacity};
            servoom_sha256_update(&t, m, 2);
            servoom_sha256_update(&l, servoom_layer_bitmap(bean, f, i), fs);
        }
    }
    free(frame);
    servoom_sha256_final(&c, digest);
    servoom_digest_to_hex(digest, 32, composite);
    servoom_sha256_final(&l, digest);
    servoom_digest_to_hex(digest, 32, layers);
    servoom_sha256_final(&t, digest);
    servoom_digest_to_hex(digest, 32, table);
}

char *tl_read_text(const char *path)
{
    FILE *fp = fopen(path, "rb");
    if (!fp)
        return NULL;
    fseek(fp, 0, SEEK_END);
    long n = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (n < 0) {
        fclose(fp);
        return NULL;
    }
    char *buf = (char *)malloc((size_t)n + 1);
    if (!buf) {
        fclose(fp);
        return NULL;
    }
    size_t got = fread(buf, 1, (size_t)n, fp);
    fclose(fp);
    buf[got] = 0;
    return buf;
}

const char *tl_corpus_dir(void)
{
    static char dir[4096];
    const char *env = getenv("SERVOOM_CORPUS_DIR");
    if (env && *env) {
        snprintf(dir, sizeof dir, "%s", env);
    } else {
        snprintf(dir, sizeof dir, "%s/corpus", SERVOOM_REPO_ROOT);
    }
    return dir;
}

int tl_webp_roundtrip(const servoom_pixel_bean *bean, char *why, size_t why_len)
{
    uint8_t *data = NULL;
    size_t len = 0;
    servoom_status st = servoom_pixel_bean_encode_webp(bean, &data, &len);
    if (st != SERVOOM_OK) {
        snprintf(why, why_len, "encode: %s", servoom_status_str(st));
        return 0;
    }
    sv_webp_anim anim;
    st = sv_webp_decode_anim(data, len, &anim);
    free(data);
    if (st != SERVOOM_OK) {
        snprintf(why, why_len, "decoding our own webp: %s", servoom_status_str(st));
        return 0;
    }
    int ok = 0;
    size_t fs = servoom_pixel_bean_frame_size(bean);
    size_t px = (size_t)bean->width * bean->height;
    if (anim.width != bean->width || anim.height != bean->height) {
        snprintf(why, why_len, "canvas %dx%d != %dx%d", anim.width, anim.height, bean->width, bean->height);
        goto done;
    }
    int wf = 0, t = 0;
    for (int f = 0; f < bean->total_frames;) {
        const uint8_t *frame = servoom_pixel_bean_frame(bean, f);
        int run = 1;
        while (f + run < bean->total_frames && memcmp(frame, servoom_pixel_bean_frame(bean, f + run), fs) == 0)
            run++;
        if (wf >= anim.num_frames) {
            snprintf(why, why_len, "webp has only %d frame(s); bean frame %d (run of %d) is missing",
                     anim.num_frames, f, run);
            goto done;
        }
        const uint8_t *rgba = anim.rgba + (size_t)wf * px * 4;
        for (size_t i = 0; i < px; i++)
            if (rgba[4 * i] != frame[3 * i] || rgba[4 * i + 1] != frame[3 * i + 1] ||
                rgba[4 * i + 2] != frame[3 * i + 2] || rgba[4 * i + 3] != 255) {
                snprintf(why, why_len, "pixel %zu of webp frame %d (bean frame %d) differs", i, wf, f);
                goto done;
            }
        t += run * bean->speed;
        /* One run in total: libwebp writes a plain still (no ANIM chunk, no timing), as
         * Pillow does for a single frame; the decoder then reports timestamp 0. */
        int still = (wf == 0 && f + run == bean->total_frames && anim.timestamps[wf] == 0);
        if (anim.timestamps[wf] != t && !still) {
            snprintf(why, why_len, "webp frame %d ends at %d ms, expected %d (bean frame %d, run of %d)",
                     wf, anim.timestamps[wf], t, f, run);
            goto done;
        }
        wf++;
        f += run;
    }
    if (wf != anim.num_frames) {
        snprintf(why, why_len, "webp has %d frames, bean has %d runs", anim.num_frames, wf);
        goto done;
    }
    ok = 1;
done:
    sv_webp_anim_free(&anim);
    return ok;
}
