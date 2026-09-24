/* Minimal test helpers shared by the test programs. */
#ifndef SERVOOM_TESTLIB_H
#define SERVOOM_TESTLIB_H

#include <stddef.h>
#include <stdint.h>
#include "servoom/servoom.h"

#define TL_SKIP 77 /* ctest SKIP_RETURN_CODE */

extern int tl_failures;
extern int tl_checks;

/* Record a check; prints on failure. Returns cond. */
int tl_check(int cond, const char *file, int line, const char *fmt, ...);
#define CHECK(cond, ...) tl_check((cond) != 0, __FILE__, __LINE__, __VA_ARGS__)

/* Exit code for main(): 0 if everything passed, 1 otherwise; prints a summary. */
int tl_finish(const char *program);

/* SHA-256 hex of every frame of a bean, concatenated (the baseline's "hash"). */
void tl_bean_hash(const servoom_pixel_bean *bean, char hex[65]);
/* SHA-256 hex of the composited frames / raw bitmaps / layer table of a layer bean. */
void tl_layer_hashes(const servoom_layer_bean *bean, char composite[65], char layers[65],
                     char table[65]);

/* Encode `bean` as an animated lossless WebP, decode it again and check pixels and timeline:
 * the WebP must hold exactly one frame per run of identical consecutive bean frames (libwebp
 * merges those), each ending at the run's cumulative speed*frames ms and carrying the run's
 * exact RGB (alpha 255). A bean that collapses to one run yields a still image with no
 * timing (as with Pillow); that is accepted. Returns 1 on success; otherwise writes the
 * reason into `why`.
 * Requires the encoder to be compiled in. */
int tl_webp_roundtrip(const servoom_pixel_bean *bean, char *why, size_t why_len);

/* Read a whole text file (malloc'd, NUL-terminated) or NULL. */
char *tl_read_text(const char *path);

/* Directory of the corpus (repo_root/corpus). */
const char *tl_corpus_dir(void);

#endif
