#pragma once
#include "contacts.h"

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

}
