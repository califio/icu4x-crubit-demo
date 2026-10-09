#pragma once
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace contacts {
struct Request {
    std::string locale = "de@collation=phonebook";
    std::vector<std::string> names;
    std::uint32_t benchmark_iterations = 0;
    bool done = false;
};
Request ParseArguments(int argc, char** argv, std::string_view backend,
                       bool allow_benchmark = false);
std::string ToLanguageTag(std::string_view locale);
void Print(const std::vector<std::string>& names);
}
