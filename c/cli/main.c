/* servoom command-line tool (C).
 *
 *   servoom info FILE...                 print a JSON summary of each .dat (format, frames,
 *                                        canvas, speed, SHA-256 of the decoded RGB frames)
 *   servoom decode FILE [-o DIR]         write every frame as frame_NNN.ppm (+ .rgb) and the
 *                                        animation as NAME.webp (lossless; --no-webp skips it)
 *   servoom decode-layer FILE [-o DIR]   composite frames (+ NAME.webp) + each raw layer bitmap
 *   servoom md5 TEXT                     MD5 hex of TEXT (for SERVOOM_MD5_PASSWORD)
 *   servoom gallery-info GALLERY_ID      print the GalleryInfo record        (needs creds)
 *   servoom download GALLERY_ID [-o DIR] download an artwork (+ layer file)  (needs creds)
 *   servoom download-user USER_ID [-o DIR] [--limit N]                       (needs creds)
 *   servoom list-category CATEGORY [--limit N] [--size MASK] [--type T]      (needs creds)
 *
 * Credentials come from SERVOOM_EMAIL plus SERVOOM_MD5_PASSWORD or SERVOOM_PASSWORD, like
 * the Python CLI. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "servoom/servoom.h"
#include "util/fs.h"

static void usage(void)
{
    fputs("usage: servoom <command> [args]\n"
          "  info FILE...\n"
          "  decode FILE [-o DIR] [--no-webp]\n"
          "  decode-layer FILE [-o DIR] [--no-webp]\n"
          "  md5 TEXT\n"
          "  gallery-info GALLERY_ID\n"
          "  download GALLERY_ID [-o DIR] [--no-layer]\n"
          "  download-user USER_ID [-o DIR] [--limit N]\n"
          "  list-category CATEGORY [--limit N] [--size MASK] [--type T]\n",
          stderr);
}

static const char *opt(int argc, char **argv, const char *name, const char *dflt)
{
    for (int i = 2; i + 1 < argc; i++)
        if (strcmp(argv[i], name) == 0)
            return argv[i + 1];
    return dflt;
}

static int has_flag(int argc, char **argv, const char *name)
{
    for (int i = 2; i < argc; i++)
        if (strcmp(argv[i], name) == 0)
            return 1;
    return 0;
}

static int format_byte(const char *path)
{
    FILE *fp = fopen(path, "rb");
    if (!fp)
        return -1;
    int b = fgetc(fp);
    fclose(fp);
    return b;
}

static void bean_hash(const servoom_pixel_bean *bean, char hex[65])
{
    servoom_sha256 ctx;
    uint8_t d[32];
    servoom_sha256_init(&ctx);
    servoom_sha256_update(&ctx, bean->frames, servoom_pixel_bean_frame_size(bean) * (size_t)bean->total_frames);
    servoom_sha256_final(&ctx, d);
    servoom_digest_to_hex(d, 32, hex);
}

static int cmd_info(int argc, char **argv)
{
    int rc = 0;
    for (int i = 2; i < argc; i++) {
        const char *path = argv[i];
        int fmt = format_byte(path);
        if (fmt < 0) {
            printf("{\"path\": \"%s\", \"error\": \"cannot read\"}\n", path);
            rc = 1;
            continue;
        }
        if (servoom_format_is_layer(fmt)) {
            servoom_layer_bean *layer = NULL;
            servoom_status st = servoom_layer_decode_file(path, &layer);
            if (st != SERVOOM_OK) {
                printf("{\"path\": \"%s\", \"kind\": \"layer\", \"format\": %d, \"error\": \"%s\"}\n", path, fmt,
                       servoom_status_str(st));
                rc = 1;
                continue;
            }
            servoom_sha256 ctx;
            uint8_t d[32];
            char hex[65];
            size_t fs = (size_t)layer->width * layer->height * 3;
            uint8_t *frame = malloc(fs);
            servoom_sha256_init(&ctx);
            for (int f = 0; f < layer->num_frames; f++) {
                servoom_layer_composite_frame(layer, f, frame);
                servoom_sha256_update(&ctx, frame, fs);
            }
            free(frame);
            servoom_sha256_final(&ctx, d);
            servoom_digest_to_hex(d, 32, hex);
            printf("{\"path\": \"%s\", \"kind\": \"layer\", \"format\": %d, \"frames\": %d, \"width\": %d, "
                   "\"height\": %d, \"total_layers\": %d, \"hash\": \"%s\"}\n",
                   path, fmt, layer->num_frames, layer->width, layer->height, layer->total_layers, hex);
            servoom_layer_bean_free(layer);
        } else {
            servoom_pixel_bean *bean = NULL;
            servoom_status st = servoom_decode_file(path, &bean);
            if (st != SERVOOM_OK) {
                printf("{\"path\": \"%s\", \"kind\": \"pixel\", \"format\": %d, \"error\": \"%s\"}\n", path, fmt,
                       servoom_status_str(st));
                rc = 1;
                continue;
            }
            char hex[65];
            bean_hash(bean, hex);
            printf("{\"path\": \"%s\", \"kind\": \"pixel\", \"format\": %d, \"frames\": %d, \"speed\": %d, "
                   "\"width\": %d, \"height\": %d, \"hash\": \"%s\"}\n",
                   path, bean->format, bean->total_frames, bean->speed, bean->width, bean->height, hex);
            servoom_pixel_bean_free(bean);
        }
    }
    return rc;
}

static int write_frames(const servoom_pixel_bean *bean, const char *dir)
{
    if (sv_mkdir_p(dir) != SERVOOM_OK) {
        fprintf(stderr, "cannot create %s\n", dir);
        return 1;
    }
    char path[4096];
    for (int f = 0; f < bean->total_frames; f++) {
        snprintf(path, sizeof path, "%s/frame_%03d.ppm", dir, f);
        if (servoom_pixel_bean_write_ppm(bean, f, path) != SERVOOM_OK) {
            fprintf(stderr, "cannot write %s\n", path);
            return 1;
        }
        snprintf(path, sizeof path, "%s/frame_%03d.rgb", dir, f);
        sv_write_file(path, servoom_pixel_bean_frame(bean, f), servoom_pixel_bean_frame_size(bean));
    }
    return 0;
}

/* Write the animation as DIR/NAME.webp (NAME = the input's basename without extension)
 * unless --no-webp was given. A library built without the encoder only warns. */
static int write_webp(const servoom_pixel_bean *bean, const char *dir, const char *src, int argc, char **argv)
{
    if (has_flag(argc, argv, "--no-webp"))
        return 0;
    if (!servoom_has_webp_encoder()) {
        fputs("note: built without the WebP encoder (SERVOOM_WITH_WEBP_ENCODER=OFF); no .webp written\n",
              stderr);
        return 0;
    }
    const char *base = src;
    for (const char *p = src; *p; p++)
        if (*p == '/' || *p == '\\')
            base = p + 1;
    const char *dot = strrchr(base, '.');
    int stem_len = dot && dot != base ? (int)(dot - base) : (int)strlen(base);
    char path[4096];
    snprintf(path, sizeof path, "%s/%.*s.webp", dir, stem_len, base);
    servoom_status st = servoom_pixel_bean_write_webp(bean, path);
    if (st != SERVOOM_OK) {
        fprintf(stderr, "cannot write %s: %s\n", path, servoom_status_str(st));
        return 1;
    }
    printf("[OK] %s\n", path);
    return 0;
}

static int cmd_decode(int argc, char **argv)
{
    if (argc < 3) {
        usage();
        return 2;
    }
    const char *path = argv[2];
    const char *dir = opt(argc, argv, "-o", "out");
    servoom_pixel_bean *bean = NULL;
    servoom_status st = servoom_decode_file(path, &bean);
    if (st != SERVOOM_OK) {
        fprintf(stderr, "decode failed: %s\n", servoom_status_str(st));
        return 1;
    }
    int rc = write_frames(bean, dir);
    if (!rc)
        rc = write_webp(bean, dir, path, argc, argv);
    if (!rc)
        printf("[OK] %s -> %s (%d frames, %dx%d, %d ms)\n", path, dir, bean->total_frames, bean->width,
               bean->height, bean->speed);
    servoom_pixel_bean_free(bean);
    return rc;
}

static int cmd_decode_layer(int argc, char **argv)
{
    if (argc < 3) {
        usage();
        return 2;
    }
    const char *path = argv[2];
    const char *dir = opt(argc, argv, "-o", "out");
    servoom_layer_bean *layer = NULL;
    servoom_status st = servoom_layer_decode_file(path, &layer);
    if (st != SERVOOM_OK) {
        fprintf(stderr, "decode failed: %s\n", servoom_status_str(st));
        return 1;
    }
    servoom_pixel_bean *bean = NULL;
    st = servoom_layer_to_pixel_bean(layer, 100, &bean);
    if (st != SERVOOM_OK) {
        fprintf(stderr, "composite failed: %s\n", servoom_status_str(st));
        servoom_layer_bean_free(layer);
        return 1;
    }
    int rc = write_frames(bean, dir);
    if (!rc)
        rc = write_webp(bean, dir, path, argc, argv);
    char p[4096];
    size_t fs = (size_t)layer->width * layer->height * 3;
    for (int f = 0; !rc && f < layer->num_frames; f++)
        for (int l = 0; l < layer->frames[f].num_layers; l++) {
            snprintf(p, sizeof p, "%s/layer_%03d_%02d_op%03d%s.rgb", dir, f, l, layer->frames[f].layers[l].opacity,
                     layer->frames[f].layers[l].hidden ? "_HIDDEN" : "");
            sv_write_file(p, servoom_layer_bitmap(layer, f, l), fs);
        }
    if (!rc)
        printf("[OK] %s -> %s (%d frames, %d layers, %dx%d)\n", path, dir, layer->num_frames,
               layer->total_layers, layer->width, layer->height);
    servoom_pixel_bean_free(bean);
    servoom_layer_bean_free(layer);
    return rc;
}

static int cmd_md5(int argc, char **argv)
{
    if (argc < 3) {
        usage();
        return 2;
    }
    char hex[33];
    servoom_md5_hex(argv[2], strlen(argv[2]), hex);
    puts(hex);
    return 0;
}

static servoom_client *make_client(void)
{
    const char *email = getenv("SERVOOM_EMAIL");
    const char *md5 = getenv("SERVOOM_MD5_PASSWORD");
    const char *plain = getenv("SERVOOM_PASSWORD");
    char buf[33];
    if (!email || !*email || (!(md5 && *md5) && !(plain && *plain))) {
        fputs("set SERVOOM_EMAIL and SERVOOM_MD5_PASSWORD (or SERVOOM_PASSWORD)\n", stderr);
        return NULL;
    }
    if (!(md5 && *md5)) {
        servoom_md5_hex(plain, strlen(plain), buf);
        md5 = buf;
    }
    servoom_client *c = servoom_client_new(email, md5, NULL);
    if (!c) {
        fputs("client init failed (built without the cloud client?)\n", stderr);
        return NULL;
    }
    servoom_status st = servoom_client_login(c);
    if (st != SERVOOM_OK) {
        fprintf(stderr, "login failed: %s (%s)\n", servoom_status_str(st), servoom_client_last_error(c));
        servoom_client_free(c);
        return NULL;
    }
    return c;
}

static int cmd_gallery_info(int argc, char **argv)
{
    if (argc < 3) {
        usage();
        return 2;
    }
    servoom_client *c = make_client();
    if (!c)
        return 1;
    cJSON *info = NULL;
    servoom_status st = servoom_client_gallery_info(c, atoll(argv[2]), &info);
    int rc = 0;
    if (st != SERVOOM_OK) {
        fprintf(stderr, "gallery info failed: %s (%s)\n", servoom_status_str(st), servoom_client_last_error(c));
        rc = 1;
    } else {
        char *txt = cJSON_Print(info);
        puts(txt);
        free(txt);
        cJSON_Delete(info);
    }
    servoom_client_free(c);
    return rc;
}

static int cmd_download(int argc, char **argv)
{
    if (argc < 3) {
        usage();
        return 2;
    }
    const char *dir = opt(argc, argv, "-o", "downloads");
    servoom_client *c = make_client();
    if (!c)
        return 1;
    char *path = NULL;
    cJSON *info = NULL;
    servoom_status st = servoom_client_download_artwork(c, atoll(argv[2]), dir, &path, &info);
    int rc = 0;
    if (st != SERVOOM_OK) {
        fprintf(stderr, "download failed: %s (%s)\n", servoom_status_str(st), servoom_client_last_error(c));
        rc = 1;
    } else {
        printf("[OK] %s\n", path);
        const cJSON *lid = cJSON_GetObjectItemCaseSensitive(info, "LayerFileId");
        if (!has_flag(argc, argv, "--no-layer") && cJSON_IsString(lid) && lid->valuestring[0]) {
            size_t n = strlen(path) + 16;
            char *lpath = malloc(n);
            snprintf(lpath, n, "%s", path);
            char *dot = strrchr(lpath, '.');
            if (dot)
                *dot = 0;
            strcat(lpath, "_layer.dat");
            st = servoom_client_download_file(c, lid->valuestring, lpath);
            if (st == SERVOOM_OK)
                printf("[OK] %s\n", lpath);
            else
                fprintf(stderr, "layer download failed: %s\n", servoom_status_str(st));
            free(lpath);
        }
        free(path);
        cJSON_Delete(info);
    }
    servoom_client_free(c);
    return rc;
}

typedef struct {
    servoom_client *c;
    const char *dir;
    int ok, failed;
} dl_ctx;

static int download_item(const cJSON *item, void *ud)
{
    dl_ctx *d = (dl_ctx *)ud;
    const cJSON *gid = cJSON_GetObjectItemCaseSensitive(item, "GalleryId");
    const cJSON *fid = cJSON_GetObjectItemCaseSensitive(item, "FileId");
    const cJSON *name = cJSON_GetObjectItemCaseSensitive(item, "FileName");
    if (!cJSON_IsNumber(gid) || !cJSON_IsString(fid)) {
        d->failed++;
        return 0;
    }
    char safe[256], path[4096];
    servoom_sanitize_filename(cJSON_IsString(name) ? name->valuestring : "art", safe, sizeof safe);
    snprintf(path, sizeof path, "%s/%lld_%s.dat", d->dir, (long long)gid->valuedouble, safe);
    servoom_status st = servoom_client_download_file(d->c, fid->valuestring, path);
    if (st == SERVOOM_OK) {
        d->ok++;
        printf("[OK] %s\n", path);
    } else {
        d->failed++;
        fprintf(stderr, "[FAIL] %lld: %s\n", (long long)gid->valuedouble, servoom_status_str(st));
    }
    return 0;
}

static int cmd_download_user(int argc, char **argv)
{
    if (argc < 3) {
        usage();
        return 2;
    }
    long long uid = atoll(argv[2]);
    char dflt[64];
    snprintf(dflt, sizeof dflt, "downloads/%lld", uid);
    const char *dir = opt(argc, argv, "-o", dflt);
    int limit = atoi(opt(argc, argv, "--limit", "0"));
    servoom_client *c = make_client();
    if (!c)
        return 1;
    if (sv_mkdir_p(dir) != SERVOOM_OK) {
        fprintf(stderr, "cannot create %s\n", dir);
        servoom_client_free(c);
        return 1;
    }
    dl_ctx d = {c, dir, 0, 0};
    servoom_status st = servoom_client_list_someone_uploads(c, uid, limit, NULL, download_item, &d);
    if (st != SERVOOM_OK)
        fprintf(stderr, "listing failed: %s (%s)\n", servoom_status_str(st), servoom_client_last_error(c));
    printf("Downloaded %d file(s), %d failed\n", d.ok, d.failed);
    servoom_client_free(c);
    return st == SERVOOM_OK && d.failed == 0 ? 0 : 1;
}

static int print_item(const cJSON *item, void *ud)
{
    (void)ud;
    const cJSON *gid = cJSON_GetObjectItemCaseSensitive(item, "GalleryId");
    const cJSON *name = cJSON_GetObjectItemCaseSensitive(item, "FileName");
    const cJSON *user = cJSON_GetObjectItemCaseSensitive(item, "UserName");
    const cJSON *likes = cJSON_GetObjectItemCaseSensitive(item, "LikeCnt");
    printf("%10lld  %-40s  by %-20s  likes %d\n", cJSON_IsNumber(gid) ? (long long)gid->valuedouble : 0,
           cJSON_IsString(name) ? name->valuestring : "?", cJSON_IsString(user) ? user->valuestring : "?",
           cJSON_IsNumber(likes) ? (int)likes->valuedouble : 0);
    return 0;
}

static int cmd_list_category(int argc, char **argv)
{
    if (argc < 3) {
        usage();
        return 2;
    }
    int limit = atoi(opt(argc, argv, "--limit", "40"));
    servoom_client *c = make_client();
    if (!c)
        return 1;
    cJSON *extra = cJSON_CreateObject();
    const char *size = opt(argc, argv, "--size", NULL);
    const char *type = opt(argc, argv, "--type", NULL);
    if (size)
        cJSON_AddNumberToObject(extra, "FileSize", atoi(size));
    if (type)
        cJSON_AddNumberToObject(extra, "FileType", atoi(type));
    servoom_status st = servoom_client_list_category(c, atoi(argv[2]), limit, extra, print_item, NULL);
    cJSON_Delete(extra);
    if (st != SERVOOM_OK)
        fprintf(stderr, "listing failed: %s (%s)\n", servoom_status_str(st), servoom_client_last_error(c));
    servoom_client_free(c);
    return st == SERVOOM_OK ? 0 : 1;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        usage();
        return 2;
    }
    const char *cmd = argv[1];
    if (strcmp(cmd, "info") == 0) return cmd_info(argc, argv);
    if (strcmp(cmd, "decode") == 0) return cmd_decode(argc, argv);
    if (strcmp(cmd, "decode-layer") == 0) return cmd_decode_layer(argc, argv);
    if (strcmp(cmd, "md5") == 0) return cmd_md5(argc, argv);
    if (strcmp(cmd, "gallery-info") == 0) return cmd_gallery_info(argc, argv);
    if (strcmp(cmd, "download") == 0) return cmd_download(argc, argv);
    if (strcmp(cmd, "download-user") == 0) return cmd_download_user(argc, argv);
    if (strcmp(cmd, "list-category") == 0) return cmd_list_category(argc, argv);
    if (strcmp(cmd, "--version") == 0) { puts(SERVOOM_VERSION_STRING); return 0; }
    usage();
    return 2;
}
