/* Tiny filesystem helpers. */
#ifndef SERVOOM_UTIL_FS_H
#define SERVOOM_UTIL_FS_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

/* Read a whole file into a malloc'd buffer (NUL-terminated as a courtesy, not counted). */
servoom_status sv_read_file(const char *path, uint8_t **out, size_t *out_len);
servoom_status sv_write_file(const char *path, const void *data, size_t len);
/* mkdir -p */
servoom_status sv_mkdir_p(const char *path);
int sv_file_exists(const char *path);

#endif
