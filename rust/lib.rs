//! Rust owns both the locale parser and the collator.
#![forbid(unsafe_code)]

use icu_collator::CollatorBorrowed;
use icu_locale_core::Locale;

pub struct Collator {
    inner: CollatorBorrowed<'static>,
}

impl Collator {
    /// Creates a collator from a BCP 47 locale identifier.
    /// Error 1 means an invalid/unsupported locale; error 2 means missing data.
    pub fn new(locale: &[u8]) -> Result<Self, u8> {
        let locale = Locale::try_from_utf8(locale).map_err(|_| 1u8)?;
        let inner = CollatorBorrowed::try_new(locale.into(), Default::default()).map_err(|_| 2u8)?;
        Ok(Self { inner })
    }

    pub fn compare_utf8(&self, left: &[u8], right: &[u8]) -> i32 {
        match self.inner.compare_utf8(left, right) {
            std::cmp::Ordering::Less => -1,
            std::cmp::Ordering::Equal => 0,
            std::cmp::Ordering::Greater => 1,
        }
    }
}
