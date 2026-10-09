#include "contacts.h"
#include "unicode/coll.h"
#include "unicode/locid.h"
#include "unicode/stringpiece.h"

#include <algorithm>
#include <exception>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>

int main(int argc, char** argv) {
    try {
        auto request = contacts::ParseArguments(argc, argv, "ICU4C 66.1");
        if (request.done) return 0;
        auto locale = icu::Locale::createFromName(request.locale.c_str());
        if (locale.isBogus()) throw std::runtime_error("Invalid locale");
        UErrorCode status = U_ZERO_ERROR;
        std::unique_ptr<icu::Collator> collator(icu::Collator::createInstance(locale, status));
        if (U_FAILURE(status) || !collator) throw std::runtime_error(u_errorName(status));
        for (const auto& name : request.names)
            if (name.size() > std::numeric_limits<int32_t>::max())
                throw std::runtime_error("Contact name is too long");
        std::stable_sort(request.names.begin(), request.names.end(),
            [&](const auto& left, const auto& right) {
                UErrorCode error = U_ZERO_ERROR;
                auto result = collator->compareUTF8(
                    icu::StringPiece(left.data(), static_cast<int32_t>(left.size())),
                    icu::StringPiece(right.data(), static_cast<int32_t>(right.size())), error);
                if (U_FAILURE(error)) throw std::runtime_error(u_errorName(error));
                return result == UCOL_LESS;
            });
        contacts::Print(request.names);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
