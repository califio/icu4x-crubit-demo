#include "crubit_collator.h"
#include "manual_collator.h"

#include <charconv>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {
using Clock = std::chrono::steady_clock;
using Pair = std::pair<std::string, std::string>;

void Require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

std::uint32_t Positive(std::string_view value) {
    std::uint32_t result = 0;
    auto [end, error] = std::from_chars(value.data(), value.data() + value.size(), result);
    Require(error == std::errc{} && end == value.data() + value.size() && result,
            "Iteration counts must be positive integers");
    return result;
}

std::int64_t Elapsed(Clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count();
}

template<class Collator>
std::int64_t Compare(const Collator& collator, const std::vector<Pair>& pairs,
                     std::uint32_t iterations) {
    std::int64_t checksum = 0;
    for (std::uint32_t i = 0; i < iterations; ++i)
        for (const auto& [left, right] : pairs)
            checksum += collator.compare_utf8(left, right);
    return checksum;
}

template<class Collator>
std::int64_t Lifecycle(std::string_view locale, const Pair& pair, std::uint32_t iterations) {
    std::int64_t checksum = 0;
    for (std::uint32_t i = 0; i < iterations; ++i) {
        Collator collator(locale);
        checksum += collator.compare_utf8(pair.first, pair.second);
    }
    return checksum;
}

struct Result {
    std::int64_t setup_ns, compare_ns, lifecycle_ns;
    std::int64_t warmup_checksum, checksum, lifecycle_warmup_checksum, lifecycle_checksum;
};

template<class Collator>
Result Measure(std::string_view locale, const std::vector<Pair>& pairs,
               std::uint32_t iterations, std::uint32_t lifecycle_iterations) {
    Result result{};
    auto start = Clock::now();
    Collator collator(locale);
    result.setup_ns = Elapsed(start);
    result.warmup_checksum = Compare(collator, pairs, 1);
    start = Clock::now();
    result.checksum = Compare(collator, pairs, iterations);
    result.compare_ns = Elapsed(start);
    result.lifecycle_warmup_checksum = Lifecycle<Collator>(locale, pairs.front(), 16);
    start = Clock::now();
    result.lifecycle_checksum = Lifecycle<Collator>(locale, pairs.front(), lifecycle_iterations);
    result.lifecycle_ns = Elapsed(start);
    return result;
}

void Print(const Result& result) {
    std::cout << "{\"setup_ns\":" << result.setup_ns
              << ",\"compare_ns\":" << result.compare_ns
              << ",\"lifecycle_ns\":" << result.lifecycle_ns
              << ",\"warmup_checksum\":" << result.warmup_checksum
              << ",\"checksum\":" << result.checksum
              << ",\"lifecycle_warmup_checksum\":" << result.lifecycle_warmup_checksum
              << ",\"lifecycle_checksum\":" << result.lifecycle_checksum << '}';
}

void CheckMatches(std::string_view locale, const std::vector<Pair>& pairs) {
    manual::Collator manual(locale);
    generated::Collator crubit(locale);
    for (const auto& [left, right] : pairs)
        Require(manual.compare_utf8(left, right) == crubit.compare_utf8(left, right),
                "Manual FFI and Crubit returned different orderings");
}

template<class Collator>
std::uint8_t ErrorCode(std::string_view locale) {
    try { Collator collator(locale); }
    catch (const CollatorError& error) { return error.code(); }
    return 0;
}

template<class Collator>
void CheckOwnership() {
    Collator source("en-US");
    Collator moved(std::move(source));
    Require(moved.compare_utf8("a", "b") == -1, "Move construction failed");
    source = std::move(moved);
    Require(source.compare_utf8("a", "b") == -1, "Move assignment failed");
    Collator other("de-u-co-phonebk");
    other = std::move(source);
    Require(other.compare_utf8("same", "same") == 0, "Replacing an owner failed");
}

void SelfTest() {
    const std::vector<Pair> pairs = {{"", ""}, {"", "x"}, {"a", "b"}, {"z", "a"},
        {"Müller", "Mueller"}, {"\r", ""}, {std::string("a\0b", 3), "a"},
        {std::string(1, static_cast<char>(0xff)), "x"}};
    for (auto locale : {"en-US", "de-u-co-phonebk", "ja", "zh"}) CheckMatches(locale, pairs);
    Require(ErrorCode<manual::Collator>("@") == 1 && ErrorCode<generated::Collator>("@") == 1,
            "Constructor errors differ");
    CheckOwnership<manual::Collator>();
    CheckOwnership<generated::Collator>();
    ManualCollatorHandle* handle = nullptr;
    Require(manual_collator_create(reinterpret_cast<const std::uint8_t*>("en"), 2, &handle) == 0
                && handle, "Raw constructor failed");
    Require(manual_collator_compare(handle, nullptr, 0, nullptr, 0) == 0,
            "Empty raw strings failed");
    manual_collator_destroy(handle);
    Require(manual_collator_create(reinterpret_cast<const std::uint8_t*>("@"), 1, &handle) == 1
                && !handle, "Failed constructor did not clear the output handle");
    manual_collator_destroy(nullptr);
    std::cout << "PASS: FFI ownership, errors, and comparisons agree\n";
}
}

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--self-test") {
            SelfTest();
            return 0;
        }
        Require(argc == 5, "Usage: ffi-bench manual-first|crubit-first LOCALE ITERATIONS LIFECYCLE_ITERATIONS");
        const std::string_view order = argv[1], locale = argv[2];
        Require(order == "manual-first" || order == "crubit-first", "Invalid execution order");
        const auto iterations = Positive(argv[3]);
        const auto lifecycle_iterations = Positive(argv[4]);
        std::vector<Pair> pairs;
        for (std::string left, right; std::getline(std::cin, left);) {
            Require(static_cast<bool>(std::getline(std::cin, right)), "Input must contain an even number of lines");
            pairs.emplace_back(std::move(left), std::move(right));
        }
        Require(!pairs.empty(), "Input must contain at least one pair");
        CheckMatches(locale, pairs);
        Result manual_result, crubit_result;
        if (order == "manual-first") {
            manual_result = Measure<manual::Collator>(locale, pairs, iterations, lifecycle_iterations);
            crubit_result = Measure<generated::Collator>(locale, pairs, iterations, lifecycle_iterations);
        } else {
            crubit_result = Measure<generated::Collator>(locale, pairs, iterations, lifecycle_iterations);
            manual_result = Measure<manual::Collator>(locale, pairs, iterations, lifecycle_iterations);
        }
        std::cout << "{\"pairs\":" << pairs.size() << ",\"iterations\":" << iterations
                  << ",\"lifecycle_iterations\":" << lifecycle_iterations << ",\"manual\":";
        Print(manual_result);
        std::cout << ",\"crubit\":";
        Print(crubit_result);
        std::cout << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
