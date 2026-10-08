#pragma once
#include <string>
#include <string_view>
#include <vector>

namespace contacts {
struct Request {
    std::string locale = "de@collation=phonebook";
    std::vector<std::string> names;
    bool done = false;
};
Request ParseArguments(int argc, char** argv, std::string_view backend);
std::string ToLanguageTag(std::string_view locale);
void Print(const std::vector<std::string>& names);
}
