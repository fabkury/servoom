#include "client/http.h"

#include <stdlib.h>
#include <string.h>

#if SERVOOM_WITH_CLIENT
#include <curl/curl.h>
#include "util/bytes.h"

#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#endif

struct sv_http {
    CURL *curl;
    char *user_agent;
    int timeout_seconds;
};

static int curl_initialized = 0;

sv_http *sv_http_new(const char *user_agent, int timeout_seconds)
{
    if (!curl_initialized) {
        if (curl_global_init(CURL_GLOBAL_DEFAULT) != 0)
            return NULL;
        curl_initialized = 1;
    }
    sv_http *h = (sv_http *)calloc(1, sizeof(*h));
    if (!h)
        return NULL;
    h->curl = curl_easy_init();
    h->user_agent = sv_strdup(user_agent ? user_agent : "servoom-c");
    h->timeout_seconds = timeout_seconds > 0 ? timeout_seconds : 10;
    if (!h->curl || !h->user_agent) {
        sv_http_free(h);
        return NULL;
    }
    return h;
}

void sv_http_free(sv_http *h)
{
    if (!h)
        return;
    if (h->curl)
        curl_easy_cleanup(h->curl);
    free(h->user_agent);
    free(h);
}

static size_t write_cb(char *ptr, size_t size, size_t nmemb, void *ud)
{
    sv_buf *b = (sv_buf *)ud;
    size_t n = size * nmemb;
    return sv_buf_append(b, ptr, n) == SERVOOM_OK ? n : 0;
}

static servoom_status perform(sv_http *h, const char *url, const char *post_body, uint8_t **out,
                              size_t *out_len, long *status_code, char *errbuf)
{
    *out = NULL;
    *out_len = 0;
    if (status_code)
        *status_code = 0;
    if (errbuf)
        errbuf[0] = 0;
    sv_buf body;
    sv_buf_init(&body);
    struct curl_slist *headers = NULL;
    CURL *c = h->curl;
    curl_easy_reset(c);
    curl_easy_setopt(c, CURLOPT_URL, url);
    curl_easy_setopt(c, CURLOPT_USERAGENT, h->user_agent);
    curl_easy_setopt(c, CURLOPT_TIMEOUT, (long)h->timeout_seconds * 6); /* whole transfer */
    curl_easy_setopt(c, CURLOPT_CONNECTTIMEOUT, (long)h->timeout_seconds);
    curl_easy_setopt(c, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(c, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(c, CURLOPT_WRITEDATA, &body);
    curl_easy_setopt(c, CURLOPT_NOSIGNAL, 1L);
    curl_easy_setopt(c, CURLOPT_ACCEPT_ENCODING, "");
    if (errbuf)
        curl_easy_setopt(c, CURLOPT_ERRORBUFFER, errbuf);
    if (post_body) {
        headers = curl_slist_append(headers, "Content-Type: application/json");
        curl_easy_setopt(c, CURLOPT_HTTPHEADER, headers);
        curl_easy_setopt(c, CURLOPT_POSTFIELDS, post_body);
        curl_easy_setopt(c, CURLOPT_POSTFIELDSIZE, (long)strlen(post_body));
    }
    CURLcode rc = curl_easy_perform(c);
    if (headers)
        curl_slist_free_all(headers);
    if (rc != CURLE_OK) {
        if (errbuf && !errbuf[0])
            snprintf(errbuf, 256, "%s", curl_easy_strerror(rc));
        sv_buf_free(&body);
        return SERVOOM_ERR_NET;
    }
    if (status_code)
        curl_easy_getinfo(c, CURLINFO_RESPONSE_CODE, status_code);
    /* NUL-terminate as a courtesy */
    if (sv_buf_append_byte(&body, 0) != SERVOOM_OK) {
        sv_buf_free(&body);
        return SERVOOM_ERR_NOMEM;
    }
    size_t n = body.len - 1;
    *out = sv_buf_detach(&body, NULL);
    *out_len = n;
    return SERVOOM_OK;
}

servoom_status sv_http_post_json(sv_http *h, const char *url, const char *body, uint8_t **out,
                                 size_t *out_len, long *status_code, char *errbuf)
{
    return perform(h, url, body ? body : "{}", out, out_len, status_code, errbuf);
}

servoom_status sv_http_get(sv_http *h, const char *url, uint8_t **out, size_t *out_len,
                           long *status_code, char *errbuf)
{
    return perform(h, url, NULL, out, out_len, status_code, errbuf);
}

void sv_sleep_ms(int ms)
{
#ifdef _WIN32
    Sleep((DWORD)(ms > 0 ? ms : 0));
#else
    struct timespec ts = {ms / 1000, (long)(ms % 1000) * 1000000L};
    nanosleep(&ts, NULL);
#endif
}

#else /* !SERVOOM_WITH_CLIENT */

sv_http *sv_http_new(const char *user_agent, int timeout_seconds)
{
    (void)user_agent; (void)timeout_seconds;
    return NULL;
}
void sv_http_free(sv_http *h) { (void)h; }
servoom_status sv_http_post_json(sv_http *h, const char *url, const char *body, uint8_t **out,
                                 size_t *out_len, long *status_code, char *errbuf)
{
    (void)h; (void)url; (void)body; (void)status_code; (void)errbuf;
    *out = NULL; *out_len = 0;
    return SERVOOM_ERR_UNSUPPORTED;
}
servoom_status sv_http_get(sv_http *h, const char *url, uint8_t **out, size_t *out_len,
                           long *status_code, char *errbuf)
{
    (void)h; (void)url; (void)status_code; (void)errbuf;
    *out = NULL; *out_len = 0;
    return SERVOOM_ERR_UNSUPPORTED;
}
void sv_sleep_ms(int ms) { (void)ms; }

#endif
