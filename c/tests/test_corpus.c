/* Corpus parity test: decode every file listed in corpus/manifest.json and compare the
 * result with corpus/baseline.json, which records what the Python decoders produce
 * (frame count, canvas, speed, SHA-256 over all decoded RGB bytes). Where the Python
 * oracle failed on a file, the C decoder must fail too (gracefully).
 *
 * The corpus payloads are local-only (git-ignored); when none are present the test is
 * skipped (exit 77). Set SERVOOM_CORPUS_DIR to point elsewhere. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cJSON.h"
#include "servoom/servoom.h"
#include "testlib.h"

typedef struct {
    int total, ok, mismatch, missing;
} stat_t;

static stat_t stats[256];
static int shown = 0;

static const char *jstr(const cJSON *o, const char *k)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(o, k);
    return cJSON_IsString(v) ? v->valuestring : NULL;
}
static int jint(const cJSON *o, const char *k, int dflt)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(o, k);
    return cJSON_IsNumber(v) ? (int)v->valuedouble : dflt;
}

static void report(const char *path, const char *why)
{
    if (shown < 40)
        fprintf(stderr, "MISMATCH %s: %s\n", path, why);
    shown++;
}

static int check_pixel(const char *path, const char *full, const cJSON *expect)
{
    servoom_pixel_bean *bean = NULL;
    servoom_status st = servoom_decode_file(full, &bean);
    const char *err = jstr(expect, "error");
    char why[512];
    if (err) {
        if (st == SERVOOM_OK) {
            snprintf(why, sizeof why, "python failed (%s) but C decoded %d frames", err, bean->total_frames);
            report(path, why);
            servoom_pixel_bean_free(bean);
            return 0;
        }
        return 1;
    }
    if (st != SERVOOM_OK) {
        snprintf(why, sizeof why, "C failed with '%s', python decoded %d frames",
                 servoom_status_str(st), jint(expect, "frames", -1));
        report(path, why);
        return 0;
    }
    char hex[65];
    tl_bean_hash(bean, hex);
    int ok = 1;
    if (bean->total_frames != jint(expect, "frames", -1) || bean->width != jint(expect, "width", -1) ||
        bean->height != jint(expect, "height", -1) || bean->speed != jint(expect, "speed", -1)) {
        snprintf(why, sizeof why, "shape C=%dx%d f=%d s=%d python=%dx%d f=%d s=%d", bean->width,
                 bean->height, bean->total_frames, bean->speed, jint(expect, "width", -1),
                 jint(expect, "height", -1), jint(expect, "frames", -1), jint(expect, "speed", -1));
        report(path, why);
        ok = 0;
    } else if (strcmp(hex, jstr(expect, "hash") ? jstr(expect, "hash") : "") != 0) {
        snprintf(why, sizeof why, "pixel hash differs (%d frames %dx%d)", bean->total_frames,
                 bean->width, bean->height);
        report(path, why);
        ok = 0;
    }
    servoom_pixel_bean_free(bean);
    return ok;
}

static int check_layer(const char *path, const char *full, const cJSON *expect)
{
    servoom_layer_bean *bean = NULL;
    servoom_status st = servoom_layer_decode_file(full, &bean);
    const char *err = jstr(expect, "error");
    char why[512];
    if (err) {
        if (st == SERVOOM_OK) {
            snprintf(why, sizeof why, "python failed (%s) but C decoded", err);
            report(path, why);
            servoom_layer_bean_free(bean);
            return 0;
        }
        return 1;
    }
    if (st != SERVOOM_OK) {
        snprintf(why, sizeof why, "C failed with '%s'", servoom_status_str(st));
        report(path, why);
        return 0;
    }
    char c[65], l[65], t[65];
    tl_layer_hashes(bean, c, l, t);
    int ok = 1;
    if (bean->num_frames != jint(expect, "frames", -1) || bean->width != jint(expect, "width", -1) ||
        bean->height != jint(expect, "height", -1) || bean->total_layers != jint(expect, "total_layers", -1)) {
        snprintf(why, sizeof why, "shape C=%d f=%d L=%d python=%d f=%d L=%d", bean->width, bean->num_frames,
                 bean->total_layers, jint(expect, "width", -1), jint(expect, "frames", -1),
                 jint(expect, "total_layers", -1));
        report(path, why);
        ok = 0;
    } else if (strcmp(t, jstr(expect, "table_hash") ? jstr(expect, "table_hash") : "") != 0) {
        report(path, "layer table differs");
        ok = 0;
    } else if (strcmp(l, jstr(expect, "layers_hash") ? jstr(expect, "layers_hash") : "") != 0) {
        report(path, "raw layer bitmaps differ");
        ok = 0;
    } else if (strcmp(c, jstr(expect, "hash") ? jstr(expect, "hash") : "") != 0) {
        report(path, "composite differs");
        ok = 0;
    }
    servoom_layer_bean_free(bean);
    return ok;
}

int main(void)
{
    const char *dir = tl_corpus_dir();
    char p[4096];
    snprintf(p, sizeof p, "%s/manifest.json", dir);
    char *mtext = tl_read_text(p);
    snprintf(p, sizeof p, "%s/baseline.json", dir);
    char *btext = tl_read_text(p);
    if (!mtext || !btext) {
        printf("corpus manifest/baseline not found under %s -- skipping\n", dir);
        return TL_SKIP;
    }
    cJSON *manifest = cJSON_Parse(mtext), *baseline = cJSON_Parse(btext);
    free(mtext);
    free(btext);
    if (!manifest || !baseline) {
        fprintf(stderr, "corpus json unparsable\n");
        return 1;
    }
    cJSON *entries = cJSON_GetObjectItemCaseSensitive(manifest, "entries");
    int present = 0, total = 0, failed = 0, no_baseline = 0;
    cJSON *e;
    cJSON_ArrayForEach(e, entries) {
        const char *rel = jstr(e, "path");
        const char *kind = jstr(e, "kind");
        int fmt = jint(e, "format", 0) & 0xFF;
        if (!rel || !kind)
            continue;
        total++;
        stats[fmt].total++;
        snprintf(p, sizeof p, "%s/%s", dir, rel);
        FILE *fp = fopen(p, "rb");
        if (!fp) {
            stats[fmt].missing++;
            continue;
        }
        fclose(fp);
        present++;
        const cJSON *expect = cJSON_GetObjectItemCaseSensitive(baseline, rel);
        if (!expect) {
            no_baseline++;
            continue;
        }
        int ok = strcmp(kind, "layer") == 0 ? check_layer(rel, p, expect) : check_pixel(rel, p, expect);
        if (ok)
            stats[fmt].ok++;
        else {
            stats[fmt].mismatch++;
            failed++;
        }
    }
    cJSON_Delete(manifest);
    cJSON_Delete(baseline);
    if (present == 0) {
        printf("corpus has %d entries but no payload files are present -- skipping "
               "(run: python corpus/corpus.py fetch)\n", total);
        return TL_SKIP;
    }
    printf("format      files  ok  mismatch  missing\n");
    for (int f = 0; f < 256; f++)
        if (stats[f].total)
            printf("0x%02x (%3d)  %5d %4d %9d %8d\n", f, f, stats[f].total, stats[f].ok, stats[f].mismatch,
                   stats[f].missing);
    printf("test_corpus: %d files present of %d, %d without baseline, %d mismatch(es)\n", present, total,
           no_baseline, failed);
    return failed ? 1 : 0;
}
