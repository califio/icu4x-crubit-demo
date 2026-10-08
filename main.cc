#include "collation.h"
#include "contacts.h"

#include <algorithm>
#include <exception>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
    try {
        auto request = contacts::ParseArguments(argc, argv, "ICU4X 2.3.1 through Crubit");
        if (request.done) return 0;
        const auto locale = contacts::ToLanguageTag(request.locale);
        auto collator = collation::Collator::new_(locale);
        if (!collator.has_value())
            throw std::runtime_error("Invalid or unsupported locale");
        std::stable_sort(request.names.begin(), request.names.end(),
            [&](const auto& left, const auto& right) {
                return collator.value().compare_utf8(left, right) < 0;
            });
        contacts::Print(request.names);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
