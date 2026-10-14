#include "pulsegen.h"
#include "common.h"
#include "rp.h"

#include <atomic>
#include <chrono>
#include <cmath>
#include <mutex>
#include <sys/mman.h>
#include <unistd.h>

namespace {
constexpr uint32_t SLOT_OFFSET = 0x00700000u;
constexpr uint32_t SUBOFFSET = 0x00020000u;
constexpr uint32_t MAP_SIZE = SUBOFFSET + 0x1000u;
constexpr uint32_t ID_VERSION = 0x50554c01u;
constexpr uint32_t REG_CONTROL = 0x04u, REG_STATUS = 0x08u;
constexpr uint32_t REG_PERIOD = 0x0cu, REG_HIGH = 0x10u, REG_COMMAND = 0x14u;
constexpr uint32_t REG_PIN = 0x1cu, REG_ACTIVE_PERIOD = 0x20u, REG_ACTIVE_HIGH = 0x24u;
constexpr uint64_t MAX_PERIOD_NS = 0xfffffffeull * 2u;
void* mapping = nullptr;
volatile uint32_t* regs = nullptr;
std::mutex mutex;

uint32_t read(uint32_t offset) { return regs[offset / 4u]; }
uint32_t settledRead(uint32_t offset) {
    uint32_t value = 0;
    for (unsigned i = 0; i < 16; ++i) value = read(offset);
    return value;
}
void write(uint32_t offset, uint32_t value) { regs[offset / 4u] = value; }

int checkMap() {
    if (regs != nullptr) return RP_OK;
    int result = cmn_Map(MAP_SIZE, SLOT_OFFSET, &mapping);
    if (result != RP_OK) return result;
    // Guard the existing common mapper's incorrect MAP_FAILED pointer check.
    if (mapping == MAP_FAILED) { mapping = nullptr; return RP_EMMD; }
    regs = reinterpret_cast<volatile uint32_t*>(static_cast<uint8_t*>(mapping) + SUBOFFSET);
    if (settledRead(0) != ID_VERSION || settledRead(0x18u) != 2u) {
        regs = nullptr;
        cmn_Unmap(MAP_SIZE, &mapping);
        mapping = nullptr;
        return RP_EUF;
    }
    return RP_OK;
}

int waitIdle() {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(100);
    do {
        const uint32_t status = settledRead(REG_STATUS);
        if (!(status & RP_PULSE_STATUS_BUSY) && (status & RP_PULSE_STATUS_READY))
            return RP_OK;
        usleep(100);
    } while (std::chrono::steady_clock::now() < deadline);
    return RP_EOP;
}

bool validTiming(uint64_t period_ns, uint64_t high_ns) {
    return period_ns >= 4u && period_ns <= MAX_PERIOD_NS && period_ns % 4u == 0u &&
           high_ns >= 2u && high_ns < period_ns && high_ns % 2u == 0u;
}

int apply(uint64_t period_ns, uint64_t high_ns, bool enable) {
    int result = waitIdle();
    if (result != RP_OK) return result;
    write(REG_COMMAND, 4u);
    write(REG_PERIOD, static_cast<uint32_t>(period_ns / 2u));
    write(REG_HIGH, static_cast<uint32_t>(high_ns / 2u));
    write(REG_CONTROL, enable ? 1u : 0u);
    std::atomic_thread_fence(std::memory_order_seq_cst);
    write(REG_COMMAND, 1u);
    // Settled reads also prevent an immediate pre-request BUSY=0 observation.
    result = waitIdle();
    if (result != RP_OK) return result;
    const uint32_t status = settledRead(REG_STATUS);
    if ((status & RP_PULSE_STATUS_ERROR) ||
        !!(status & RP_PULSE_STATUS_ENABLED) != enable ||
        settledRead(REG_ACTIVE_PERIOD) != period_ns / 2u ||
        settledRead(REG_ACTIVE_HIGH) != high_ns / 2u)
        return RP_EOP;
    return RP_OK;
}

int prepareTimingChange() {
    int result = checkMap();
    if (result != RP_OK) return result;
    result = waitIdle();
    if (result != RP_OK) return result;
    return (settledRead(REG_STATUS) & RP_PULSE_STATUS_ENABLED) ? RP_EOP : RP_OK;
}
} // namespace

int pulsegen_Release() {
    const std::lock_guard<std::mutex> lock(mutex);
    regs = nullptr;
    if (mapping == nullptr) return RP_OK;
    int result = cmn_Unmap(MAP_SIZE, &mapping);
    mapping = nullptr;
    return result;
}

int rp_PulseSetTiming(uint64_t period_ns, uint64_t high_ns) {
    if (!validTiming(period_ns, high_ns)) return RP_EOOR;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = prepareTimingChange();
    return result == RP_OK ? apply(period_ns, high_ns, false) : result;
}

int rp_PulseGetTiming(uint64_t* period_ns, uint64_t* high_ns) {
    if (period_ns == nullptr || high_ns == nullptr) return RP_UIA;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = checkMap();
    if (result != RP_OK) return result;
    result = waitIdle();
    if (result != RP_OK) return result;
    *period_ns = static_cast<uint64_t>(settledRead(REG_ACTIVE_PERIOD)) * 2u;
    *high_ns = static_cast<uint64_t>(settledRead(REG_ACTIVE_HIGH)) * 2u;
    return RP_OK;
}

int rp_PulseSetFrequency(double frequency_hz) {
    if (!std::isfinite(frequency_hz) || frequency_hz < 1e9 / MAX_PERIOD_NS || frequency_hz > 250e6)
        return RP_EOOR;
    const uint64_t cycles = static_cast<uint64_t>(std::llround(250e6 / frequency_hz));
    const uint64_t period_ns = cycles * 4u;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = prepareTimingChange();
    if (result != RP_OK) return result;
    const double duty = static_cast<double>(settledRead(REG_ACTIVE_HIGH)) /
                        settledRead(REG_ACTIVE_PERIOD);
    uint64_t high_ticks = static_cast<uint64_t>(std::llround(cycles * 2u * duty));
    if (high_ticks < 1u) high_ticks = 1u;
    if (high_ticks >= cycles * 2u) high_ticks = cycles * 2u - 1u;
    return apply(period_ns, high_ticks * 2u, false);
}

int rp_PulseSetPeriod(uint64_t period_ns) {
    if (period_ns < 4u || period_ns > MAX_PERIOD_NS || period_ns % 4u != 0u)
        return RP_EOOR;
    return rp_PulseSetFrequency(1e9 / static_cast<double>(period_ns));
}

int rp_PulseGetFrequency(double* frequency_hz) {
    if (frequency_hz == nullptr) return RP_UIA;
    uint64_t period_ns = 0, high_ns = 0;
    int result = rp_PulseGetTiming(&period_ns, &high_ns);
    if (result == RP_OK) *frequency_hz = 1e9 / static_cast<double>(period_ns);
    return result;
}

int rp_PulseSetHighTime(uint64_t high_ns) {
    const std::lock_guard<std::mutex> lock(mutex);
    int result = prepareTimingChange();
    if (result != RP_OK) return result;
    uint64_t period_ns = static_cast<uint64_t>(settledRead(REG_ACTIVE_PERIOD)) * 2u;
    if (!validTiming(period_ns, high_ns)) return RP_EOOR;
    return apply(period_ns, high_ns, false);
}

int rp_PulseSetEnabled(bool enable) {
    const std::lock_guard<std::mutex> lock(mutex);
    int result = checkMap();
    if (result != RP_OK) return result;
    result = waitIdle();
    if (result != RP_OK) return result;
    const uint32_t status = settledRead(REG_STATUS);
    if (!!(status & RP_PULSE_STATUS_ENABLED) == enable) return RP_OK;
    uint64_t period_ns = static_cast<uint64_t>(settledRead(REG_ACTIVE_PERIOD)) * 2u;
    uint64_t high_ns = static_cast<uint64_t>(settledRead(REG_ACTIVE_HIGH)) * 2u;
    if (!validTiming(period_ns, high_ns)) return RP_EOP;
    return apply(period_ns, high_ns, enable);
}

int rp_PulseGetEnabled(bool* enable) {
    if (enable == nullptr) return RP_UIA;
    uint32_t status = 0;
    int result = rp_PulseGetStatus(&status);
    if (result == RP_OK) *enable = (status & RP_PULSE_STATUS_ENABLED) != 0u;
    return result;
}

int rp_PulseGetStatus(uint32_t* status) {
    if (status == nullptr) return RP_UIA;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = checkMap();
    if (result == RP_OK) *status = settledRead(REG_STATUS);
    return result;
}

int rp_PulseGetPin(rp_dpin_t* pin) {
    if (pin == nullptr) return RP_UIA;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = checkMap();
    if (result != RP_OK) return result;
    const uint32_t index = settledRead(REG_PIN);
    if (index > 7u) return RP_EOP; // this API targets 3.3 V positive-bank GPIOs
    *pin = static_cast<rp_dpin_t>(static_cast<unsigned>(RP_DIO0_P) + index);
    return RP_OK;
}

int rp_PulseReset() {
    const std::lock_guard<std::mutex> lock(mutex);
    int result = checkMap();
    if (result != RP_OK) return result;
    result = waitIdle();
    if (result != RP_OK) return result;
    write(REG_COMMAND, 2u);
    result = waitIdle();
    if (result != RP_OK) return result;
    return (settledRead(REG_STATUS) & (RP_PULSE_STATUS_ENABLED | RP_PULSE_STATUS_CLAIMED |
                                     RP_PULSE_STATUS_ERROR)) ? RP_EOP : RP_OK;
}
