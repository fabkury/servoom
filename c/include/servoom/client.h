/* Divoom cloud client: login, gallery lookups, paginated listings and file downloads.
 *
 * Port of servoom.client.DivoomClient / servoom.http. Requests are JSON POSTs to
 * app.divoom-gz.com; files are fetched from f.divoom-gz.com. Responses are handed back as
 * cJSON trees (vendored, see third_party/cJSON) that the caller owns and frees with
 * cJSON_Delete().
 *
 * Only available when the library is built with SERVOOM_WITH_CLIENT (the default); the
 * functions still exist otherwise and return SERVOOM_ERR_UNSUPPORTED.
 */
#ifndef SERVOOM_CLIENT_H
#define SERVOOM_CLIENT_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/status.h"
#include "cJSON.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct servoom_client servoom_client;

typedef struct servoom_client_settings {
    int batch_size;         /* listing window size per request (default 40) */
    int max_retries;        /* transport retries (default 3) */
    int timeout_seconds;    /* per request (default 10) */
    int retry_delay_ms;     /* pause between retries (default 1000) */
    int respect_hide_flag;  /* drop items with HideFlag set (default 1) */
    int file_size_filter;   /* FileSize bitmask for listings (default 0b111111 = all sizes) */
    const char *user_agent; /* default "Aurabox/3.1.10 (iPad; iOS 14.8; Scale/2.00)" */
} servoom_client_settings;

/* Fill `s` with the defaults the Python client uses. */
void servoom_client_settings_default(servoom_client_settings *s);

/* `md5_password` is the 32-char hex MD5 of the plain password (see servoom_md5_hex).
 * `settings` may be NULL for defaults. Returns NULL on allocation failure. */
servoom_client *servoom_client_new(const char *email, const char *md5_password,
                                   const servoom_client_settings *settings);
void servoom_client_free(servoom_client *client);

servoom_status servoom_client_login(servoom_client *client);
int servoom_client_is_logged_in(const servoom_client *client);
int64_t servoom_client_user_id(const servoom_client *client);
const char *servoom_client_token(const servoom_client *client);

/* Last error detail (transport message or the API's ReturnMessage); static per client. */
const char *servoom_client_last_error(const servoom_client *client);

/* Raw authenticated POST: `payload` (may be NULL) gets Token/UserId merged in. The parsed
 * response is returned in *out regardless of ReturnCode; the status is SERVOOM_ERR_API when
 * ReturnCode != 0. */
servoom_status servoom_client_post(servoom_client *client, const char *path,
                                   const cJSON *payload, cJSON **out);

/* Single-shot lookups (ReturnCode must be 0, else SERVOOM_ERR_API and *out == NULL). */
servoom_status servoom_client_gallery_info(servoom_client *client, int64_t gallery_id, cJSON **out);
servoom_status servoom_client_someone_info(servoom_client *client, int64_t user_id, cJSON **out);
servoom_status servoom_client_tag_info(servoom_client *client, const char *tag_name, cJSON **out);
/* UserList / TagList arrays (detached from the response; empty array if none). */
servoom_status servoom_client_search_user(servoom_client *client, const char *query, cJSON **out_list);
servoom_status servoom_client_search_tag(servoom_client *client, const char *query, cJSON **out_list);

/* Paginated listings. `on_item` is called once per kept item (the cJSON node is owned by the
 * page and valid only during the callback; return non-zero to stop early). `limit` <= 0 means
 * no limit. `extra` (may be NULL) adds/overrides payload fields, like the Python **extra. */
typedef int (*servoom_item_fn)(const cJSON *item, void *userdata);

servoom_status servoom_client_list_my_uploads(servoom_client *c, int limit, const cJSON *extra,
                                              servoom_item_fn on_item, void *userdata);
servoom_status servoom_client_list_someone_uploads(servoom_client *c, int64_t user_id, int limit,
                                                   const cJSON *extra, servoom_item_fn on_item,
                                                   void *userdata);
servoom_status servoom_client_list_category(servoom_client *c, int category_id, int limit,
                                            const cJSON *extra, servoom_item_fn on_item,
                                            void *userdata);
servoom_status servoom_client_list_tag_gallery(servoom_client *c, const char *tag_name, int limit,
                                               const cJSON *extra, servoom_item_fn on_item,
                                               void *userdata);
servoom_status servoom_client_search_gallery(servoom_client *c, const char *query, int limit,
                                             const cJSON *extra, servoom_item_fn on_item,
                                             void *userdata);
servoom_status servoom_client_list_like_users(servoom_client *c, int64_t gallery_id, int limit,
                                              servoom_item_fn on_item, void *userdata);

/* Convenience: collect a listing into a cJSON array (caller frees with cJSON_Delete). */
servoom_status servoom_client_collect_someone_uploads(servoom_client *c, int64_t user_id,
                                                      int limit, cJSON **out_array);

/* Download any cloud file (an artwork FileId or a LayerFileId). No login needed. */
servoom_status servoom_client_download_file(servoom_client *client, const char *file_id,
                                            const char *output_path);
servoom_status servoom_client_download_memory(servoom_client *client, const char *file_id,
                                              uint8_t **out_data, size_t *out_len);

/* Fetch gallery metadata, then download its artwork file into `output_dir` as
 * "<gallery_id>_<sanitized FileName>.dat" (Python naming). `out_path` receives a malloc'd
 * path the caller frees. `out_info` (optional) receives the GalleryInfo response. */
servoom_status servoom_client_download_artwork(servoom_client *client, int64_t gallery_id,
                                               const char *output_dir, char **out_path,
                                               cJSON **out_info);

/* Sanitize a file name for Windows/Unix (same rules as servoom.util.sanitize_filename);
 * writes at most `cap-1` chars + NUL. */
void servoom_sanitize_filename(const char *name, char *out, size_t cap);

#ifdef __cplusplus
}
#endif
#endif
