#include "util/fs.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>

#ifdef _WIN32
#include <direct.h>
#define sv_mkdir(p) _mkdir(p)
#else
#define sv_mkdir(p) mkdir(p, 0777)
#endif

servoom_status sv_read_file(const char *path, uint8_t **out, size_t *out_len)
{
    *out = NULL;
    *out_len = 0;
    FILE *fp = fopen(path, "rb");
    if (!fp)
        return SERVOOM_ERR_IO;
    size_t cap = 1 << 16, len = 0;
    uint8_t *buf = (uint8_t *)malloc(cap + 1);
    if (!buf) {
        fclose(fp);
        return SERVOOM_ERR_NOMEM;
    }
    for (;;) {
        if (len == cap) {
            cap *= 2;
            uint8_t *p = (uint8_t *)realloc(buf, cap + 1);
            if (!p) {
                free(buf);
                fclose(fp);
                return SERVOOM_ERR_NOMEM;
            }
            buf = p;
        }
        size_t n = fread(buf + len, 1, cap - len, fp);
        len += n;
        if (n == 0) {
            if (ferror(fp)) {
                free(buf);
                fclose(fp);
                return SERVOOM_ERR_IO;
            }
            break;
        }
    }
    fclose(fp);
    buf[len] = 0;
    *out = buf;
    *out_len = len;
    return SERVOOM_OK;
}

servoom_status sv_write_file(const char *path, const void *data, size_t len)
{
    FILE *fp = fopen(path, "wb");
    if (!fp)
        return SERVOOM_ERR_IO;
    size_t n = len ? fwrite(data, 1, len, fp) : 0;
    int bad = ferror(fp);
    fclose(fp);
    return (n == len && !bad) ? SERVOOM_OK : SERVOOM_ERR_IO;
}

int sv_file_exists(const char *path)
{
    struct stat st;
    return stat(path, &st) == 0;
}

servoom_status sv_mkdir_p(const char *path)
{
    size_t n = strlen(path);
    if (n == 0)
        return SERVOOM_OK;
    char *tmp = (char *)malloc(n + 1);
    if (!tmp)
        return SERVOOM_ERR_NOMEM;
    memcpy(tmp, path, n + 1);
    for (size_t i = 1; i <= n; i++) {
        if (tmp[i] == '/' || tmp[i] == '\\' || tmp[i] == 0) {
            char saved = tmp[i];
            tmp[i] = 0;
            /* Skip drive roots like "C:" and existing dirs. */
            if (!(i == 2 && tmp[1] == ':') && !sv_file_exists(tmp)) {
                if (sv_mkdir(tmp) != 0 && !sv_file_exists(tmp)) {
                    free(tmp);
                    return SERVOOM_ERR_IO;
                }
            }
            tmp[i] = saved;
        }
    }
    free(tmp);
    return SERVOOM_OK;
}
