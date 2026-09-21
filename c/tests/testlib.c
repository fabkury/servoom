#include "testlib.h"

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
