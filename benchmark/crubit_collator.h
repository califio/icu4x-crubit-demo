#pragma once
#include "collation.h"
#include "collator_error.h"

#include <string_view>
#include <utility>

namespace generated {
class Collator {
    static collation::Collator Create(std::string_view locale) {
        auto result = collation::Collator::new_(locale);
        if (!result.has_value()) throw CollatorError(result.error());
        return std::move(result).value();
    }
public:
    explicit Collator(std::string_view locale) : inner_(Create(locale)) {}
    Collator(Collator&&) noexcept = default;
    Collator& operator=(Collator&&) noexcept = default;
    Collator(const Collator&) = delete;
    Collator& operator=(const Collator&) = delete;
    std::int32_t compare_utf8(std::string_view left, std::string_view right) const {
        return inner_.compare_utf8(left, right);
    }
private:
    collation::Collator inner_;
};
}
