#include "codec/zstd_util.h"

#include <stdlib.h>
#include <string.h>
#include <zstd.h>
#include "util/bytes.h"

servoom_status sv_zstd_decompress(const uint8_t *in, size_t in_len, int strict, size_t max_out,
                                  uint8_t **out, size_t *out_len)
{
    *out = NULL;
    *out_len = 0;
    if (strict) {
        unsigned long long declared = ZSTD_getFrameContentSize(in, in_len);
        if (declared == ZSTD_CONTENTSIZE_ERROR || declared == ZSTD_CONTENTSIZE_UNKNOWN)
            return SERVOOM_ERR_CODEC; /* python-zstandard: "could not determine content size" */
        if (max_out && declared > max_out)
            return SERVOOM_ERR_CODEC;
    }
    ZSTD_DStream *ds = ZSTD_createDStream();
    if (!ds)
        return SERVOOM_ERR_NOMEM;
    size_t rc = ZSTD_initDStream(ds);
    if (ZSTD_isError(rc)) {
        ZSTD_freeDStream(ds);
        return SERVOOM_ERR_CODEC;
    }
    sv_buf buf;
    sv_buf_init(&buf);
    size_t chunk_cap = ZSTD_DStreamOutSize();
    uint8_t *chunk = (uint8_t *)malloc(chunk_cap);
    if (!chunk) {
        ZSTD_freeDStream(ds);
        return SERVOOM_ERR_NOMEM;
    }
    ZSTD_inBuffer zin = {in, in_len, 0};
    servoom_status st = SERVOOM_OK;
    int frame_done = 0;
    while (zin.pos < zin.size && !frame_done) {
        ZSTD_outBuffer zout = {chunk, chunk_cap, 0};
        rc = ZSTD_decompressStream(ds, &zout, &zin);
        if (ZSTD_isError(rc)) {
            st = SERVOOM_ERR_CODEC;
            break;
        }
        if (zout.pos) {
            st = sv_buf_append(&buf, chunk, zout.pos);
            if (st != SERVOOM_OK)
                break;
            if (max_out && buf.len > max_out) {
                st = SERVOOM_ERR_CODEC;
                break;
            }
        }
        frame_done = (rc == 0);
    }
    free(chunk);
    ZSTD_freeDStream(ds);
    if (st == SERVOOM_OK && strict) {
        if (!frame_done || zin.pos != zin.size)
            st = SERVOOM_ERR_CODEC;
    }
    if (st != SERVOOM_OK) {
        sv_buf_free(&buf);
        return st;
    }
    if (buf.len == 0) {
        sv_buf_free(&buf);
        *out = (uint8_t *)malloc(1);
        return *out ? SERVOOM_OK : SERVOOM_ERR_NOMEM;
    }
    *out = sv_buf_detach(&buf, out_len);
    return SERVOOM_OK;
}
