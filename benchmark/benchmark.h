#pragma once
#include "contacts.h"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <utility>

namespace contacts {
using BenchmarkClock = std::chrono::steady_clock;

inline auto Nanoseconds(BenchmarkClock::duration duration) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();
}

// FNV-1a over length-prefixed UTF-8 names, matching benchmark.py.
inline std::uint64_t SortChecksum(const std::vector<std::string>& names) {
    std::uint64_t hash = 14695981039346656037ULL;
    const auto add = [&](std::uint8_t byte) {
        hash = (hash ^ byte) * 1099511628211ULL;
    };
    for (const auto& name : names) {
        const std::uint64_t size = name.size();
        for (unsigned shift = 0; shift < 64; shift += 8)
            add(static_cast<std::uint8_t>(size >> shift));
        for (unsigned char byte : name) add(byte);
    }
    return hash;
}

template <typename Compare>
void ComparePairsAndPrint(const Request& request, Compare compare,
                          BenchmarkClock::duration setup) {
    if (request.names.empty() || request.names.size() % 2)
        throw std::runtime_error("Pair benchmark requires a nonempty, even number of names");
    std::vector<std::pair<std::string_view, std::string_view>> pairs;
    pairs.reserve(request.names.size() / 2);
    for (std::size_t i = 0; i < request.names.size(); i += 2)
        pairs.emplace_back(request.names[i], request.names[i + 1]);
    const auto run = [&](std::uint32_t iterations) {
        std::uint64_t hash = 14695981039346656037ULL;
        for (std::uint32_t i = 0; i < iterations; ++i)
            for (const auto& [left, right] : pairs)
                hash = (hash ^ static_cast<std::uint64_t>(compare(left, right) + 1))
                     * 1099511628211ULL;
        return hash;
    };
    const auto warmup = run(1);
    const auto start = BenchmarkClock::now();
    const auto checksum = run(request.benchmark_iterations);
    const auto elapsed = BenchmarkClock::now() - start;
    std::cout << "{\"iterations\":" << request.benchmark_iterations
              << ",\"pairs\":" << pairs.size()
              << ",\"setup_ns\":" << Nanoseconds(setup)
              << ",\"compare_ns\":" << Nanoseconds(elapsed)
              << ",\"warmup_checksum\":" << warmup
              << ",\"checksum\":" << checksum << "}\n";
}

template <typename Compare>
void RunCollation(Request& request, Compare compare, BenchmarkClock::duration setup) {
    if (request.benchmark_pairs) {
        ComparePairsAndPrint(request, compare, setup);
        return;
    }
    const auto less = [&](const auto& left, const auto& right) {
        return compare(left, right) < 0;
    };
    if (!request.benchmark_iterations) {
        std::stable_sort(request.names.begin(), request.names.end(), less);
        Print(request.names);
        return;
    }

    // Warm the collator and establish the expected result outside the timer.
    auto expected = request.names;
    std::stable_sort(expected.begin(), expected.end(), less);
    BenchmarkClock::duration elapsed{};
    for (std::uint32_t i = 0; i < request.benchmark_iterations; ++i) {
        auto names = request.names;
        const auto start = BenchmarkClock::now();
        std::stable_sort(names.begin(), names.end(), less);
        elapsed += BenchmarkClock::now() - start;
        if (names != expected) throw std::runtime_error("Inconsistent sort result");
    }
    std::cout << "{\"iterations\":" << request.benchmark_iterations
              << ",\"names\":" << request.names.size()
              << ",\"setup_ns\":" << Nanoseconds(setup)
              << ",\"sort_ns\":" << Nanoseconds(elapsed)
              << ",\"checksum\":" << SortChecksum(expected) << "}\n";
}
}
