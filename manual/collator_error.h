#pragma once
#include <cstdint>
#include <stdexcept>
#include <string>

class CollatorError : public std::runtime_error {
public:
    explicit CollatorError(std::uint8_t code)
        : std::runtime_error("collator error " + std::to_string(code)), code_(code) {}
    std::uint8_t code() const noexcept { return code_; }
private:
    std::uint8_t code_;
};
