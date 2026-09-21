/* servoom status codes. Every fallible function returns one of these. */
#ifndef SERVOOM_STATUS_H
#define SERVOOM_STATUS_H

#ifdef __cplusplus
extern "C" {
#endif

typedef enum servoom_status {
    SERVOOM_OK = 0,
    SERVOOM_ERR_ARG,        /* invalid argument (NULL pointer, out-of-range index) */
    SERVOOM_ERR_NOMEM,      /* allocation failed */
    SERVOOM_ERR_IO,         /* file could not be read/written */
    SERVOOM_ERR_FORMAT,     /* unsupported container format byte */
    SERVOOM_ERR_CORRUPT,    /* the data does not parse as the format claims */
    SERVOOM_ERR_CODEC,      /* a codec (LZO, zstd, JPEG, WebP, GIF, AES) rejected its input */
    SERVOOM_ERR_STATE,      /* wrong object state (e.g. client not logged in) */
    SERVOOM_ERR_NET,        /* transport failure */
    SERVOOM_ERR_JSON,       /* response is not the JSON we expect */
    SERVOOM_ERR_API,        /* the Divoom API answered with a non-zero ReturnCode */
    SERVOOM_ERR_UNSUPPORTED /* feature compiled out (e.g. client without SERVOOM_WITH_CLIENT) */
} servoom_status;

/* Human-readable name of a status code (static string, never NULL). */
const char *servoom_status_str(servoom_status status);

#ifdef __cplusplus
}
#endif
#endif
