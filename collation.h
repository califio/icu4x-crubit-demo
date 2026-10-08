#pragma once

// Single-include C++ API, following the safe-bindings examples.
#include "crubit/locale_collator.h"  // IWYU pragma: export

namespace collation {
using Collator = ::locale_collator::Collator;
}
