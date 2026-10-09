#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ManualCollatorHandle ManualCollatorHandle;
// out must be valid. Success returns 0 and an owned handle; errors return
// the Rust adapter's code and set *out to NULL. A zero-length input may be NULL.
uint8_t manual_collator_create(const uint8_t* locale, size_t len,
                              ManualCollatorHandle** out);
// Requires a live handle and readable input ranges. Returns -1, 0, or 1.
int32_t manual_collator_compare(const ManualCollatorHandle*,
                               const uint8_t* left, size_t left_len,
                               const uint8_t* right, size_t right_len);
// Accepts NULL. Each non-NULL handle must be destroyed exactly once.
void manual_collator_destroy(ManualCollatorHandle*);

#ifdef __cplusplus
}
#endif
