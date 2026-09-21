/* Internal HTTP transport for the Divoom client (libcurl). */
#ifndef SERVOOM_CLIENT_HTTP_H
#define SERVOOM_CLIENT_HTTP_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"

typedef struct sv_http sv_http;

sv_http *sv_http_new(const char *user_agent, int timeout_seconds);
void sv_http_free(sv_http *h);

/* POST `body` as application/json; the response body is returned malloc'd (+NUL).
 * `*status_code` receives the HTTP status. `errbuf` (256 bytes) gets the transport
 * message on failure. */
servoom_status sv_http_post_json(sv_http *h, const char *url, const char *body, uint8_t **out,
                                 size_t *out_len, long *status_code, char *errbuf);

/* GET `url` into memory. */
servoom_status sv_http_get(sv_http *h, const char *url, uint8_t **out, size_t *out_len,
                           long *status_code, char *errbuf);

/* Sleep for `ms` milliseconds (retry delay). */
void sv_sleep_ms(int ms);

#endif
