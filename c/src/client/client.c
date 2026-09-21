/* Divoom cloud client. Port of servoom.client.DivoomClient + servoom.http. */
#include "servoom/client.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "client/http.h"
#include "util/bytes.h"
#include "util/fs.h"

#define API_HOST "app.divoom-gz.com"
#define FILE_HOST "f.divoom-gz.com"

#define EP_USER_LOGIN "/UserLogin"
#define EP_GALLERY_INFO "/Cloud/GalleryInfo"
#define EP_MY_UPLOADS "/GetMyUploadListV3"
#define EP_LIKE_USERS "/Cloud/GetLikeUserList"
#define EP_SOMEONE_INFO "/GetSomeoneInfoV2"
#define EP_SOMEONE_LIST "/GetSomeoneListV2"
#define EP_CATEGORY_FILES "/GetCategoryFileListV2"
#define EP_SEARCH_USER "/SearchUser"
#define EP_SEARCH_TAG "/Tag/SearchTagMoreV2"
#define EP_SEARCH_GALLERY "/SearchGalleryV3"
#define EP_TAG_INFO "/Tag/GetTagInfo"
#define EP_TAG_GALLERY "/Tag/GetTagGalleryListV3"

#define ALL_FILE_SIZES 0x3F

struct servoom_client {
    char *email;
    char *md5_password;
    servoom_client_settings settings;
    char *user_agent; /* owned copy for settings.user_agent */
    sv_http *http;
    char *token;
    int token_is_number; /* echo it back as a JSON number, exactly as received */
    int64_t user_id;
    char last_error[512];
};

void servoom_client_settings_default(servoom_client_settings *s)
{
    if (!s)
        return;
    memset(s, 0, sizeof(*s));
    s->batch_size = 40;
    s->max_retries = 3;
    s->timeout_seconds = 10;
    s->retry_delay_ms = 1000;
    s->respect_hide_flag = 1;
    s->file_size_filter = ALL_FILE_SIZES;
    s->user_agent = "Aurabox/3.1.10 (iPad; iOS 14.8; Scale/2.00)";
}

servoom_client *servoom_client_new(const char *email, const char *md5_password,
                                   const servoom_client_settings *settings)
{
    if (!email || !md5_password)
        return NULL;
    servoom_client *c = (servoom_client *)calloc(1, sizeof(*c));
    if (!c)
        return NULL;
    if (settings)
        c->settings = *settings;
    else
        servoom_client_settings_default(&c->settings);
    if (c->settings.batch_size <= 0)
        c->settings.batch_size = 40;
    if (c->settings.max_retries <= 0)
        c->settings.max_retries = 1;
    c->email = sv_strdup(email);
    c->md5_password = sv_strdup(md5_password);
    c->user_agent = sv_strdup(c->settings.user_agent ? c->settings.user_agent
                                                     : "Aurabox/3.1.10 (iPad; iOS 14.8; Scale/2.00)");
    c->settings.user_agent = c->user_agent;
    c->http = sv_http_new(c->user_agent, c->settings.timeout_seconds);
    if (!c->email || !c->md5_password || !c->user_agent || (!c->http && SERVOOM_WITH_CLIENT)) {
        servoom_client_free(c);
        return NULL;
    }
    return c;
}

void servoom_client_free(servoom_client *c)
{
    if (!c)
        return;
    sv_http_free(c->http);
    free(c->email);
    free(c->md5_password);
    free(c->user_agent);
    free(c->token);
    free(c);
}

const char *servoom_client_last_error(const servoom_client *c) { return c ? c->last_error : ""; }
int servoom_client_is_logged_in(const servoom_client *c) { return c && c->token && c->user_id != 0; }
int64_t servoom_client_user_id(const servoom_client *c) { return c ? c->user_id : 0; }
const char *servoom_client_token(const servoom_client *c) { return c ? c->token : NULL; }

static void set_error(servoom_client *c, const char *msg)
{
    snprintf(c->last_error, sizeof c->last_error, "%s", msg ? msg : "");
}

/* ---- transport ---------------------------------------------------------- */

/* POST payload JSON to API path with retries; parse JSON. Python DivoomSession.post_json:
 * retries transport errors, then `.json()` (ValueError on non-JSON -> SERVOOM_ERR_JSON). */
static servoom_status post_raw(servoom_client *c, const char *path, const cJSON *payload, cJSON **out)
{
    *out = NULL;
#if !SERVOOM_WITH_CLIENT
    (void)path; (void)payload;
    set_error(c, "built without SERVOOM_WITH_CLIENT");
    return SERVOOM_ERR_UNSUPPORTED;
#else
    char url[1024];
    snprintf(url, sizeof url, "https://" API_HOST "%s%s", path[0] == '/' ? "" : "/", path);
    char *body = payload ? cJSON_PrintUnformatted(payload) : sv_strdup("{}");
    if (!body)
        return SERVOOM_ERR_NOMEM;
    servoom_status st = SERVOOM_ERR_NET;
    uint8_t *resp = NULL;
    size_t resp_len = 0;
    char errbuf[256] = {0};
    for (int attempt = 0; attempt < c->settings.max_retries; attempt++) {
        long code = 0;
        st = sv_http_post_json(c->http, url, body, &resp, &resp_len, &code, errbuf);
        if (st == SERVOOM_OK)
            break;
        if (attempt + 1 < c->settings.max_retries)
            sv_sleep_ms(c->settings.retry_delay_ms);
    }
    free(body);
    if (st != SERVOOM_OK) {
        set_error(c, errbuf[0] ? errbuf : "transport failure");
        return st;
    }
    cJSON *json = cJSON_ParseWithLength((const char *)resp, resp_len);
    free(resp);
    if (!json) {
        set_error(c, "response is not JSON");
        return SERVOOM_ERR_JSON;
    }
    *out = json;
    return SERVOOM_OK;
#endif
}

static int return_code(const cJSON *resp)
{
    const cJSON *rc = cJSON_GetObjectItemCaseSensitive(resp, "ReturnCode");
    return cJSON_IsNumber(rc) ? (int)rc->valuedouble : 0;
}

static void note_api_error(servoom_client *c, const cJSON *resp)
{
    const cJSON *msg = cJSON_GetObjectItemCaseSensitive(resp, "ReturnMessage");
    char buf[512];
    snprintf(buf, sizeof buf, "ReturnCode %d%s%s", return_code(resp),
             cJSON_IsString(msg) ? ": " : "", cJSON_IsString(msg) ? msg->valuestring : "");
    set_error(c, buf);
}

/* Copy every member of `src` into `dst` (overriding). */
static servoom_status merge_into(cJSON *dst, const cJSON *src)
{
    const cJSON *item;
    cJSON_ArrayForEach(item, src) {
        if (!item->string)
            continue;
        cJSON *dup = cJSON_Duplicate(item, 1);
        if (!dup)
            return SERVOOM_ERR_NOMEM;
        cJSON_DeleteItemFromObjectCaseSensitive(dst, item->string);
        cJSON_AddItemToObject(dst, item->string, dup);
    }
    return SERVOOM_OK;
}

static servoom_status auth_payload(servoom_client *c, const cJSON *payload, cJSON **out)
{
    *out = NULL;
    if (!servoom_client_is_logged_in(c)) {
        set_error(c, "Not logged in! Call login() first.");
        return SERVOOM_ERR_STATE;
    }
    cJSON *p = cJSON_CreateObject();
    if (!p)
        return SERVOOM_ERR_NOMEM;
    if (c->token_is_number)
        cJSON_AddNumberToObject(p, "Token", strtod(c->token, NULL));
    else
        cJSON_AddStringToObject(p, "Token", c->token);
    cJSON_AddNumberToObject(p, "UserId", (double)c->user_id);
    if (payload && merge_into(p, payload) != SERVOOM_OK) {
        cJSON_Delete(p);
        return SERVOOM_ERR_NOMEM;
    }
    *out = p;
    return SERVOOM_OK;
}

/* ---- auth --------------------------------------------------------------- */
servoom_status servoom_client_login(servoom_client *c)
{
    if (!c)
        return SERVOOM_ERR_ARG;
    cJSON *p = cJSON_CreateObject();
    if (!p)
        return SERVOOM_ERR_NOMEM;
    cJSON_AddStringToObject(p, "Email", c->email);
    cJSON_AddStringToObject(p, "Password", c->md5_password);
    cJSON *resp = NULL;
    servoom_status st = post_raw(c, EP_USER_LOGIN, p, &resp);
    cJSON_Delete(p);
    if (st != SERVOOM_OK)
        return st;
    const cJSON *uid = cJSON_GetObjectItemCaseSensitive(resp, "UserId");
    const cJSON *tok = cJSON_GetObjectItemCaseSensitive(resp, "Token");
    /* The API returns Token as a JSON number; accept a string too. */
    if (!cJSON_IsNumber(uid) || uid->valuedouble <= 0 || !(cJSON_IsNumber(tok) || cJSON_IsString(tok))) {
        note_api_error(c, resp); /* Python: KeyError -> login False */
        cJSON_Delete(resp);
        return SERVOOM_ERR_API;
    }
    free(c->token);
    if (cJSON_IsNumber(tok)) {
        char buf[32];
        snprintf(buf, sizeof buf, "%.0f", tok->valuedouble);
        c->token = sv_strdup(buf);
        c->token_is_number = 1;
    } else {
        c->token = sv_strdup(tok->valuestring);
        c->token_is_number = 0;
    }
    c->user_id = (int64_t)uid->valuedouble;
    cJSON_Delete(resp);
    if (!c->token)
        return SERVOOM_ERR_NOMEM;
    c->last_error[0] = 0;
    return SERVOOM_OK;
}

servoom_status servoom_client_post(servoom_client *c, const char *path, const cJSON *payload, cJSON **out)
{
    if (!c || !path || !out)
        return SERVOOM_ERR_ARG;
    *out = NULL;
    cJSON *p = NULL;
    servoom_status st = auth_payload(c, payload, &p);
    if (st != SERVOOM_OK)
        return st;
    st = post_raw(c, path, p, out);
    cJSON_Delete(p);
    if (st != SERVOOM_OK)
        return st;
    if (return_code(*out) != 0) {
        note_api_error(c, *out);
        return SERVOOM_ERR_API;
    }
    return SERVOOM_OK;
}

/* ---- single-shot lookups (Python _lookup: ReturnCode != 0 -> None) ------- */
static servoom_status lookup(servoom_client *c, const char *path, cJSON *payload, cJSON **out)
{
    *out = NULL;
    cJSON *resp = NULL;
    servoom_status st = servoom_client_post(c, path, payload, &resp);
    cJSON_Delete(payload);
    if (st != SERVOOM_OK) {
        cJSON_Delete(resp);
        return st;
    }
    *out = resp;
    return SERVOOM_OK;
}

servoom_status servoom_client_gallery_info(servoom_client *c, int64_t gallery_id, cJSON **out)
{
    if (!c || !out)
        return SERVOOM_ERR_ARG;
    cJSON *p = cJSON_CreateObject();
    if (!p)
        return SERVOOM_ERR_NOMEM;
    cJSON_AddNumberToObject(p, "GalleryId", (double)gallery_id);
    servoom_status st = lookup(c, EP_GALLERY_INFO, p, out);
    if (st == SERVOOM_OK) {
        /* not always echoed back */
        cJSON_DeleteItemFromObjectCaseSensitive(*out, "GalleryId");
        cJSON_AddNumberToObject(*out, "GalleryId", (double)gallery_id);
    }
    return st;
}

servoom_status servoom_client_someone_info(servoom_client *c, int64_t user_id, cJSON **out)
{
    if (!c || !out)
        return SERVOOM_ERR_ARG;
    cJSON *p = cJSON_CreateObject();
    if (!p)
        return SERVOOM_ERR_NOMEM;
    cJSON_AddNumberToObject(p, "SomeOneUserId", (double)user_id);
    return lookup(c, EP_SOMEONE_INFO, p, out);
}

servoom_status servoom_client_tag_info(servoom_client *c, const char *tag_name, cJSON **out)
{
    if (!c || !out || !tag_name)
        return SERVOOM_ERR_ARG;
    cJSON *p = cJSON_CreateObject();
    if (!p)
        return SERVOOM_ERR_NOMEM;
    cJSON_AddStringToObject(p, "TagName", tag_name);
    return lookup(c, EP_TAG_INFO, p, out);
}

static servoom_status search_list(servoom_client *c, const char *path, const char *query,
                                  const char *list_key, cJSON **out_list)
{
    if (!c || !query || !out_list)
        return SERVOOM_ERR_ARG;
    *out_list = NULL;
    cJSON *p = cJSON_CreateObject();
    if (!p)
        return SERVOOM_ERR_NOMEM;
    cJSON_AddStringToObject(p, "Keywords", query);
    cJSON *resp = NULL;
    servoom_status st = lookup(c, path, p, &resp);
    if (st == SERVOOM_ERR_API) {
        /* Python: (resp or {}).get(list, []) -> empty list, not an error */
        *out_list = cJSON_CreateArray();
        return *out_list ? SERVOOM_OK : SERVOOM_ERR_NOMEM;
    }
    if (st != SERVOOM_OK)
        return st;
    cJSON *list = cJSON_DetachItemFromObjectCaseSensitive(resp, list_key);
    cJSON_Delete(resp);
    if (!list || !cJSON_IsArray(list)) {
        cJSON_Delete(list);
        list = cJSON_CreateArray();
    }
    *out_list = list;
    return list ? SERVOOM_OK : SERVOOM_ERR_NOMEM;
}

servoom_status servoom_client_search_user(servoom_client *c, const char *query, cJSON **out_list)
{
    return search_list(c, EP_SEARCH_USER, query, "UserList", out_list);
}

servoom_status servoom_client_search_tag(servoom_client *c, const char *query, cJSON **out_list)
{
    return search_list(c, EP_SEARCH_TAG, query, "TagList", out_list);
}

/* ---- pagination (Python servoom.http.paginate) --------------------------- */
static const cJSON *first_nonempty_list(const cJSON *data, const char *const *keys)
{
    for (int i = 0; keys[i]; i++) {
        const cJSON *v = cJSON_GetObjectItemCaseSensitive(data, keys[i]);
        if (cJSON_IsArray(v) && cJSON_GetArraySize(v) > 0)
            return v;
    }
    return NULL;
}

static servoom_status paginate(servoom_client *c, const char *path, cJSON *base_payload,
                               const char *const *list_keys, int keep_hidden_check, int limit,
                               servoom_item_fn on_item, void *ud)
{
    servoom_status st = SERVOOM_OK;
    int start = 1, collected = 0, batch = c->settings.batch_size;
    for (;;) {
        cJSON_DeleteItemFromObjectCaseSensitive(base_payload, "StartNum");
        cJSON_DeleteItemFromObjectCaseSensitive(base_payload, "EndNum");
        cJSON_AddNumberToObject(base_payload, "StartNum", start);
        cJSON_AddNumberToObject(base_payload, "EndNum", start + batch - 1);
        cJSON *p = NULL;
        st = auth_payload(c, base_payload, &p);
        if (st != SERVOOM_OK)
            break;
        cJSON *resp = NULL;
        st = post_raw(c, path, p, &resp);
        cJSON_Delete(p);
        if (st == SERVOOM_ERR_JSON) { /* Python: warning, stop */
            st = SERVOOM_OK;
            break;
        }
        if (st != SERVOOM_OK)
            break;
        if (return_code(resp) != 0) { /* Python: debug log, stop */
            cJSON_Delete(resp);
            break;
        }
        const cJSON *items = first_nonempty_list(resp, list_keys);
        if (!items) {
            cJSON_Delete(resp);
            break;
        }
        int stop = 0;
        const cJSON *item;
        cJSON_ArrayForEach(item, items) {
            if (keep_hidden_check && c->settings.respect_hide_flag) {
                const cJSON *hf = cJSON_GetObjectItemCaseSensitive(item, "HideFlag");
                if ((cJSON_IsNumber(hf) && hf->valuedouble != 0) || cJSON_IsTrue(hf))
                    continue;
            }
            if (on_item && on_item(item, ud) != 0) {
                stop = 1;
                break;
            }
            collected++;
            if (limit > 0 && collected >= limit) {
                stop = 1;
                break;
            }
        }
        cJSON_Delete(resp);
        if (stop)
            break;
        start += batch;
    }
    cJSON_Delete(base_payload);
    return st;
}

static cJSON *payload_with_extra(const cJSON *extra)
{
    cJSON *p = cJSON_CreateObject();
    if (p && extra && merge_into(p, extra) != SERVOOM_OK) {
        cJSON_Delete(p);
        return NULL;
    }
    return p;
}

servoom_status servoom_client_list_my_uploads(servoom_client *c, int limit, const cJSON *extra,
                                              servoom_item_fn on_item, void *ud)
{
    static const char *const keys[] = {"FileList", NULL};
    if (!c)
        return SERVOOM_ERR_ARG;
    cJSON *p = cJSON_CreateObject();
    if (!p)
        return SERVOOM_ERR_NOMEM;
    cJSON_AddNumberToObject(p, "Version", 99);
    cJSON_AddNumberToObject(p, "FileSize", c->settings.file_size_filter);
    cJSON_AddNumberToObject(p, "RefreshIndex", 0);
    cJSON_AddNumberToObject(p, "FileSort", 0);
    if (extra && merge_into(p, extra) != SERVOOM_OK) {
        cJSON_Delete(p);
        return SERVOOM_ERR_NOMEM;
    }
    return paginate(c, EP_MY_UPLOADS, p, keys, 1, limit, on_item, ud);
}

servoom_status servoom_client_list_someone_uploads(servoom_client *c, int64_t user_id, int limit,
                                                   const cJSON *extra, servoom_item_fn on_item, void *ud)
{
    static const char *const keys[] = {"FileList", NULL};
    if (!c)
        return SERVOOM_ERR_ARG;
    cJSON *p = cJSON_CreateObject();
    if (!p)
        return SERVOOM_ERR_NOMEM;
    cJSON_AddNumberToObject(p, "Version", 99);
    cJSON_AddNumberToObject(p, "ShowAllFlag", 1);
    cJSON_AddNumberToObject(p, "SomeOneUserId", (double)user_id);
    cJSON_AddNumberToObject(p, "FileSize", c->settings.file_size_filter);
    cJSON_AddNumberToObject(p, "RefreshIndex", 0);
    cJSON_AddNumberToObject(p, "FileSort", 0);
    if (extra && merge_into(p, extra) != SERVOOM_OK) {
        cJSON_Delete(p);
        return SERVOOM_ERR_NOMEM;
    }
    return paginate(c, EP_SOMEONE_LIST, p, keys, 1, limit, on_item, ud);
}

servoom_status servoom_client_list_category(servoom_client *c, int category_id, int limit,
                                            const cJSON *extra, servoom_item_fn on_item, void *ud)
{
    static const char *const keys[] = {"FileList", "CategoryFileList", NULL};
    if (!c)
        return SERVOOM_ERR_ARG;
    cJSON *p = cJSON_CreateObject();
    if (!p)
        return SERVOOM_ERR_NOMEM;
    cJSON_AddNumberToObject(p, "Classify", category_id);
    cJSON_AddNumberToObject(p, "FileSize", c->settings.file_size_filter);
    cJSON_AddNumberToObject(p, "FileType", 5);
    cJSON_AddNumberToObject(p, "FileSort", 0);
    cJSON_AddNumberToObject(p, "Version", 12);
    cJSON_AddNumberToObject(p, "RefreshIndex", 0);
    if (extra && merge_into(p, extra) != SERVOOM_OK) {
        cJSON_Delete(p);
        return SERVOOM_ERR_NOMEM;
    }
    return paginate(c, EP_CATEGORY_FILES, p, keys, 1, limit, on_item, ud);
}

servoom_status servoom_client_list_tag_gallery(servoom_client *c, const char *tag_name, int limit,
                                               const cJSON *extra, servoom_item_fn on_item, void *ud)
{
    static const char *const keys[] = {"FileList", NULL};
    if (!c || !tag_name)
        return SERVOOM_ERR_ARG;
    cJSON *p = payload_with_extra(extra);
    if (!p)
        return SERVOOM_ERR_NOMEM;
    cJSON_DeleteItemFromObjectCaseSensitive(p, "TagName");
    cJSON_AddStringToObject(p, "TagName", tag_name);
    return paginate(c, EP_TAG_GALLERY, p, keys, 1, limit, on_item, ud);
}

servoom_status servoom_client_search_gallery(servoom_client *c, const char *query, int limit,
                                             const cJSON *extra, servoom_item_fn on_item, void *ud)
{
    static const char *const keys[] = {"FileList", NULL};
    if (!c || !query)
        return SERVOOM_ERR_ARG;
    cJSON *p = payload_with_extra(extra);
    if (!p)
        return SERVOOM_ERR_NOMEM;
    cJSON_DeleteItemFromObjectCaseSensitive(p, "Keywords");
    cJSON_AddStringToObject(p, "Keywords", query);
    return paginate(c, EP_SEARCH_GALLERY, p, keys, 1, limit, on_item, ud);
}

servoom_status servoom_client_list_like_users(servoom_client *c, int64_t gallery_id, int limit,
                                              servoom_item_fn on_item, void *ud)
{
    static const char *const keys[] = {"UserList", NULL};
    if (!c)
        return SERVOOM_ERR_ARG;
    cJSON *p = cJSON_CreateObject();
    if (!p)
        return SERVOOM_ERR_NOMEM;
    cJSON_AddNumberToObject(p, "GalleryId", (double)gallery_id);
    return paginate(c, EP_LIKE_USERS, p, keys, 1, limit, on_item, ud);
}

static int collect_cb(const cJSON *item, void *ud)
{
    cJSON *arr = (cJSON *)ud;
    cJSON *dup = cJSON_Duplicate(item, 1);
    if (dup)
        cJSON_AddItemToArray(arr, dup);
    return 0;
}

servoom_status servoom_client_collect_someone_uploads(servoom_client *c, int64_t user_id, int limit,
                                                      cJSON **out_array)
{
    if (!out_array)
        return SERVOOM_ERR_ARG;
    *out_array = cJSON_CreateArray();
    if (!*out_array)
        return SERVOOM_ERR_NOMEM;
    servoom_status st = servoom_client_list_someone_uploads(c, user_id, limit, NULL, collect_cb, *out_array);
    if (st != SERVOOM_OK) {
        cJSON_Delete(*out_array);
        *out_array = NULL;
    }
    return st;
}

/* ---- downloads ---------------------------------------------------------- */
servoom_status servoom_client_download_memory(servoom_client *c, const char *file_id,
                                              uint8_t **out_data, size_t *out_len)
{
    if (!c || !file_id || !out_data || !out_len)
        return SERVOOM_ERR_ARG;
    *out_data = NULL;
    *out_len = 0;
#if !SERVOOM_WITH_CLIENT
    set_error(c, "built without SERVOOM_WITH_CLIENT");
    return SERVOOM_ERR_UNSUPPORTED;
#else
    char url[2048];
    snprintf(url, sizeof url, "https://" FILE_HOST "/%s", file_id);
    char errbuf[256] = {0};
    long code = 0;
    servoom_status st = sv_http_get(c->http, url, out_data, out_len, &code, errbuf);
    if (st != SERVOOM_OK) {
        set_error(c, errbuf[0] ? errbuf : "download failed");
        return st;
    }
    if (code >= 400) { /* raise_for_status */
        char msg[128];
        snprintf(msg, sizeof msg, "HTTP %ld downloading file", code);
        set_error(c, msg);
        free(*out_data);
        *out_data = NULL;
        *out_len = 0;
        return SERVOOM_ERR_NET;
    }
    return SERVOOM_OK;
#endif
}

servoom_status servoom_client_download_file(servoom_client *c, const char *file_id, const char *output_path)
{
    if (!output_path)
        return SERVOOM_ERR_ARG;
    uint8_t *data = NULL;
    size_t len = 0;
    servoom_status st = servoom_client_download_memory(c, file_id, &data, &len);
    if (st != SERVOOM_OK)
        return st;
    st = sv_write_file(output_path, data, len);
    free(data);
    if (st != SERVOOM_OK)
        set_error(c, "could not write output file");
    return st;
}

void servoom_sanitize_filename(const char *name, char *out, size_t cap)
{
    if (!out || cap == 0)
        return;
    out[0] = 0;
    if (!name)
        return;
    size_t n = 0;
    for (const char *p = name; *p && n + 1 < cap && n < 200; p++) {
        char ch = *p;
        if (strchr("<>:\"/\\|?*", ch))
            ch = '_';
        out[n++] = ch;
    }
    out[n] = 0;
    /* strip leading/trailing '.' and ' ' */
    size_t start = 0;
    while (out[start] == '.' || out[start] == ' ')
        start++;
    size_t end = n;
    while (end > start && (out[end - 1] == '.' || out[end - 1] == ' '))
        end--;
    memmove(out, out + start, end - start);
    out[end - start] = 0;
    if (strlen(out) > 200)
        out[200] = 0;
}

servoom_status servoom_client_download_artwork(servoom_client *c, int64_t gallery_id, const char *output_dir,
                                               char **out_path, cJSON **out_info)
{
    if (out_path)
        *out_path = NULL;
    if (out_info)
        *out_info = NULL;
    if (!c)
        return SERVOOM_ERR_ARG;
    cJSON *info = NULL;
    servoom_status st = servoom_client_gallery_info(c, gallery_id, &info);
    if (st != SERVOOM_OK)
        return st;
    const cJSON *fid = cJSON_GetObjectItemCaseSensitive(info, "FileId");
    const cJSON *fname = cJSON_GetObjectItemCaseSensitive(info, "FileName");
    if (!cJSON_IsString(fid) || !fid->valuestring[0]) {
        set_error(c, "PixelBean missing FileId in metadata");
        cJSON_Delete(info);
        return SERVOOM_ERR_JSON;
    }
    const char *dir = output_dir && *output_dir ? output_dir : "downloads";
    if ((st = sv_mkdir_p(dir)) != SERVOOM_OK) {
        set_error(c, "could not create output directory");
        cJSON_Delete(info);
        return st;
    }
    char raw_name[256], safe[256];
    if (cJSON_IsString(fname) && fname->valuestring[0])
        snprintf(raw_name, sizeof raw_name, "%s", fname->valuestring);
    else
        snprintf(raw_name, sizeof raw_name, "art_%lld", (long long)gallery_id);
    servoom_sanitize_filename(raw_name, safe, sizeof safe);
    size_t plen = strlen(dir) + strlen(safe) + 64;
    char *path = (char *)malloc(plen);
    if (!path) {
        cJSON_Delete(info);
        return SERVOOM_ERR_NOMEM;
    }
    snprintf(path, plen, "%s/%lld_%s.dat", dir, (long long)gallery_id, safe);
    st = servoom_client_download_file(c, fid->valuestring, path);
    if (st != SERVOOM_OK) {
        free(path);
        cJSON_Delete(info);
        return st;
    }
    if (out_path)
        *out_path = path;
    else
        free(path);
    if (out_info)
        *out_info = info;
    else
        cJSON_Delete(info);
    return SERVOOM_OK;
}
