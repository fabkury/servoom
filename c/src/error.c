#include "servoom/status.h"

const char *servoom_status_str(servoom_status status)
{
    switch (status) {
    case SERVOOM_OK:              return "ok";
    case SERVOOM_ERR_ARG:         return "invalid argument";
    case SERVOOM_ERR_NOMEM:       return "out of memory";
    case SERVOOM_ERR_IO:          return "i/o error";
    case SERVOOM_ERR_FORMAT:      return "unsupported format";
    case SERVOOM_ERR_CORRUPT:     return "corrupt data";
    case SERVOOM_ERR_CODEC:       return "codec error";
    case SERVOOM_ERR_STATE:       return "invalid state";
    case SERVOOM_ERR_NET:         return "network error";
    case SERVOOM_ERR_JSON:        return "unexpected json";
    case SERVOOM_ERR_API:         return "api error";
    case SERVOOM_ERR_UNSUPPORTED: return "feature not built";
    }
    return "unknown status";
}
