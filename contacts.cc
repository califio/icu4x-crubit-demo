#include "contacts.h"
#include <algorithm>
#include <cstdio>
#include <iostream>
#include <stdexcept>
#include <utility>

namespace contacts {
namespace {
std::string CveLocale() {
    std::string locale = "de";
    for (int i = 1; i <= 18; ++i) {
        char variant[12];
        std::snprintf(variant, sizeof(variant), "-aaaaaa%02d", i);
        locale += variant;
    }
    return locale + "@collation=phonebook";
}
}

Request ParseArguments(int argc, char** argv, std::string_view backend) {
    Request request;
    bool options = true;
    bool trigger = false;
    bool read_stdin = false;
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (options && arg == "--") { options = false; continue; }
        if (options && (arg == "--help" || arg == "-h")) {
            std::cout << "Usage: " << argv[0] << " [--locale LOCALE | --cve] [--stdin] [--] NAME...\n"
                         "With no names, sort the example contact list.\n"
                         "--cve uses the CVE-2021-30535 locale.\n"
                         "--stdin reads additional names, one per line.\n"
                         "--version prints the backend version.\n";
            request.done = true;
            return request;
        }
        if (options && arg == "--version") {
            std::cout << backend << '\n';
            request.done = true;
            return request;
        }
        if (options && arg == "--locale") {
            if (++i == argc) throw std::runtime_error("--locale requires a value");
            request.locale = argv[i];
        } else if (options && arg == "--cve") {
            trigger = true;
        } else if (options && arg == "--stdin") {
            read_stdin = true;
        } else if (options && arg.starts_with("--")) {
            throw std::runtime_error("Unknown option: " + arg);
        } else {
            request.names.push_back(std::move(arg));
        }
    }
    if (trigger) request.locale = CveLocale();
    if (read_stdin)
        for (std::string line; std::getline(std::cin, line);)
            request.names.push_back(std::move(line));
    if (request.names.empty() && !read_stdin)
        request.names = {"Zimmermann", "Müller", "Andersson", "Özil", "Mueller", "Meyer"};
    return request;
}

std::string ToLanguageTag(std::string_view locale) {
    const auto separator = locale.find('@');
    std::string tag(locale.substr(0, separator));
    std::replace(tag.begin(), tag.end(), '_', '-');
    if (separator == std::string_view::npos) return tag;

    // The demo supports only the legacy ICU collation keyword. Reject other
    // legacy options so the migration cannot silently change their meaning.
    auto keyword = locale.substr(separator + 1);
    constexpr std::string_view prefix = "collation=";
    if (!keyword.starts_with(prefix))
        throw std::runtime_error("Invalid or unsupported locale");
    auto value = keyword.substr(prefix.size());
    if (value.empty() || value.find_first_of(";@") != std::string_view::npos)
        throw std::runtime_error("Invalid or unsupported locale");
    if (value == "phonebook") value = "phonebk";
    else if (value == "traditional") value = "trad";
    else if (value == "dictionary") value = "dict";
    tag += "-u-co-";
    tag += value;
    return tag;
}

void Print(const std::vector<std::string>& names) {
    for (const auto& name : names) std::cout << name << '\n';
}
}
