//! Handwritten C ABI used only by the benchmark.
#![deny(unsafe_op_in_unsafe_fn)]

use locale_collator::Collator;
use std::{ptr, slice};

unsafe fn bytes<'a>(data: *const u8, len: usize) -> &'a [u8] {
    if len == 0 {
        &[]
    } else {
        // SAFETY: The caller keeps a readable range of len bytes alive.
        unsafe { slice::from_raw_parts(data, len) }
    }
}

/// Returns the adapter's error code, or zero and an owned handle on success.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn manual_collator_create(
    locale: *const u8, len: usize, out: *mut *mut Collator,
) -> u8 {
    // SAFETY: The caller supplies a valid output slot and readable locale.
    unsafe { *out = ptr::null_mut() };
    match Collator::new(unsafe { bytes(locale, len) }) {
        Ok(collator) => {
            unsafe { *out = Box::into_raw(Box::new(collator)) };
            0
        }
        Err(code) => code,
    }
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn manual_collator_compare(
    collator: *const Collator,
    left: *const u8, left_len: usize,
    right: *const u8, right_len: usize,
) -> i32 {
    // SAFETY: The handle is live and both input ranges remain readable.
    unsafe { (&*collator).compare_utf8(bytes(left, left_len), bytes(right, right_len)) }
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn manual_collator_destroy(collator: *mut Collator) {
    if !collator.is_null() {
        // SAFETY: Each owned handle is returned exactly once.
        unsafe { drop(Box::from_raw(collator)) };
    }
}
