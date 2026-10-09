#pragma once
#include "collator_error.h"
#include "manual_ffi.h"

#include <cassert>
#include <memory>
#include <string_view>

namespace manual {
class Collator {
    struct Deleter {
        void operator()(ManualCollatorHandle* value) const noexcept {
            manual_collator_destroy(value);
        }
    };
    using Handle = std::unique_ptr<ManualCollatorHandle, Deleter>;

    static const std::uint8_t* Bytes(std::string_view text) {
        return reinterpret_cast<const std::uint8_t*>(text.data());
    }
    static Handle Create(std::string_view locale) {
        ManualCollatorHandle* value = nullptr;
        auto code = manual_collator_create(Bytes(locale), locale.size(), &value);
        if (code != 0) throw CollatorError(code);
        return Handle(value);
    }

public:
    explicit Collator(std::string_view locale) : inner_(Create(locale)) {}
    Collator(Collator&&) noexcept = default;
    Collator& operator=(Collator&&) noexcept = default;
    Collator(const Collator&) = delete;
    Collator& operator=(const Collator&) = delete;

    // A moved-from owner may be destroyed or assigned a new value.
    std::int32_t compare_utf8(std::string_view left, std::string_view right) const {
        assert(inner_);
        return manual_collator_compare(inner_.get(), Bytes(left), left.size(),
                                       Bytes(right), right.size());
    }

private:
    Handle inner_;
};
}
