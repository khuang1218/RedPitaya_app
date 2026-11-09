#include "dac_spi.h"
#include "common.h"
#include "custom_mmio.h"
#include "rp.h"

#include <atomic>
#include <chrono>
#include <cmath>
#include <mutex>
#include <sys/mman.h>
#include <unistd.h>

namespace {
constexpr uint32_t MAP_SIZE = 0x41000u, SUBOFFSET = 0x40000u;
constexpr uint32_t COMMAND = 0x04u, STATUS = 0x08u, PERIOD = 0x0cu;
constexpr uint32_t WEIGHTS = 0x10u, TX = 0x20u, RX = 0x24u;
constexpr uint32_t APPLIES = 0x28u, FRAMES = 0x2cu, CLOCK_HZ = 0x30u;
constexpr uint32_t LDAC_TICKS = 0x34u, APPLIED = 0x40u;
void* mapping = nullptr;
volatile uint32_t* regs = nullptr;
std::mutex mutex;

uint32_t read(uint32_t offset) {
    uint32_t value = 0;
    for (unsigned i = 0; i < 16; ++i) value = custom_mmio_Read(regs + offset / 4u);
    return value;
}
void write(uint32_t offset, uint32_t value) {
    custom_mmio_Write(regs + offset / 4u, value);
}
int checkMap() {
    if (regs) return RP_OK;
    uint32_t version = 0;
    int result = rp_TdcWidthGetVersion(&version);
    if (result != RP_OK) return result;
    if (version != 19u) return RP_EUF;
    result = cmn_Map(MAP_SIZE, 0x00700000u, &mapping);
    if (result != RP_OK) return result;
    if (mapping == MAP_FAILED || mapping == nullptr) { mapping = nullptr; return RP_EMMD; }
    regs = reinterpret_cast<volatile uint32_t*>(static_cast<uint8_t*>(mapping) + SUBOFFSET);
    if (read(0) != 0x44414301u || read(CLOCK_HZ) != 125000000u) {
        regs = nullptr;
        cmn_Unmap(MAP_SIZE, &mapping);
        mapping = nullptr;
        return RP_EUF;
    }
    return RP_OK;
}
int waitIdle(bool startup = true) {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(100);
    unsigned spins = 0;
    do {
        const uint32_t status = read(STATUS);
        if (!(status & RP_DAC_SPI_BUSY) && (!startup || (status & RP_DAC_SPI_READY))) return RP_OK;
        if (++spins > 64) usleep(50);
    } while (std::chrono::steady_clock::now() < deadline);
    return RP_EOP;
}
int prepare() {
    int result = checkMap();
    return result == RP_OK ? waitIdle() : result;
}
int writeChecked(uint32_t offset, uint32_t value) {
    write(offset, value);
    return read(offset) == value ? RP_OK : RP_EOP;
}
int command(uint32_t cmd, uint32_t frames, uint32_t applies) {
    const uint32_t before_frames = read(FRAMES), before_applies = read(APPLIES);
    write(COMMAND, 32u);
    if (read(STATUS) & RP_DAC_SPI_DONE) return RP_EOP;
    write(COMMAND, cmd);
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(100);
    unsigned spins = 0;
    do {
        const uint32_t status = read(STATUS);
        if (!(status & RP_DAC_SPI_BUSY) && (status & RP_DAC_SPI_DONE)) {
            return read(FRAMES) == before_frames + frames && read(APPLIES) == before_applies + applies
                ? RP_OK : RP_EOP;
        }
        if (++spins > 64) usleep(50);
    } while (std::chrono::steady_clock::now() < deadline);
    // Never retry a timed-out command: the physical transaction may still finish.
    return RP_EOP;
}
} // namespace

int dacspi_Release() {
    const std::lock_guard<std::mutex> lock(mutex);
    regs = nullptr;
    if (!mapping) return RP_OK;
    int result = cmn_Unmap(MAP_SIZE, &mapping);
    mapping = nullptr;
    return result;
}

int rp_DacSpiGetStatus(uint32_t* status) {
    if (!status) return RP_UIA;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = checkMap();
    if (result == RP_OK) *status = read(STATUS);
    return result;
}
int rp_DacSpiSetPeriod(uint32_t ticks) {
    if (ticks < 4u || ticks > 250u) return RP_EOOR;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = prepare();
    return result == RP_OK ? writeChecked(PERIOD, ticks) : result;
}
int rp_DacSpiGetPeriod(uint32_t* ticks) {
    if (!ticks) return RP_UIA;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = checkMap();
    if (result == RP_OK) *ticks = read(PERIOD);
    return result;
}
int rp_DacSpiGetFrequency(double* frequency_hz) {
    if (!frequency_hz) return RP_UIA;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = checkMap();
    if (result != RP_OK) return result;
    const uint32_t ticks = read(PERIOD);
    if (ticks < 4u || ticks > 250u) return RP_EUF;
    *frequency_hz = static_cast<double>(read(CLOCK_HZ)) / ticks;
    return RP_OK;
}
int rp_DacSpiSetFrequency(double frequency_hz) {
    if (!std::isfinite(frequency_hz) || frequency_hz < 500000.0 || frequency_hz > 31250000.0)
        return RP_EOOR;
    return rp_DacSpiSetPeriod(static_cast<uint32_t>(std::ceil(125000000.0 / frequency_hz)));
}
int rp_DacSpiSetLdacWidth(uint32_t ticks) {
    if (ticks < 13u || ticks > 250u) return RP_EOOR;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = prepare();
    return result == RP_OK ? writeChecked(LDAC_TICKS, ticks) : result;
}
int rp_DacSpiGetLdacWidth(uint32_t* ticks) {
    if (!ticks) return RP_UIA;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = checkMap();
    if (result == RP_OK) *ticks = read(LDAC_TICKS);
    return result;
}
int rp_DacSpiSetWeights(const uint16_t* codes, bool apply) {
    if (!codes) return RP_UIA;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = prepare();
    if (result != RP_OK) return result;
    for (unsigned i = 0; i < 4; ++i) {
        result = writeChecked(WEIGHTS + 4u * i, codes[i]);
        if (result != RP_OK) return result;
    }
    result = command(apply ? 1u : 2u, 4u, apply ? 1u : 0u);
    if (result != RP_OK) return result;
    const uint32_t required = RP_DAC_SPI_LOADED | (apply ? RP_DAC_SPI_APPLIED : 0u);
    if ((read(STATUS) & required) != required) return RP_EOP;
    if (apply) for (unsigned i = 0; i < 4; ++i)
        if (read(APPLIED + i * 4u) != codes[i]) return RP_EOP;
    return RP_OK;
}
int rp_DacSpiGetWeights(uint16_t* codes, bool applied) {
    if (!codes) return RP_UIA;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = checkMap();
    if (result != RP_OK) return result;
    if (applied) {
        // A command can remain active after an earlier caller timed out.
        // Do not mix old/new group words across its eventual LDAC completion.
        result = waitIdle(false);
        if (result != RP_OK) return result;
    }
    if (applied && !(read(STATUS) & RP_DAC_SPI_APPLIED)) return RP_EIPV;
    for (unsigned i = 0; i < 4; ++i) codes[i] = static_cast<uint16_t>(read((applied ? APPLIED : WEIGHTS) + i * 4u));
    return RP_OK;
}
int rp_DacSpiApply() {
    const std::lock_guard<std::mutex> lock(mutex);
    int result = prepare();
    if (result != RP_OK) return result;
    if (!(read(STATUS) & RP_DAC_SPI_LOADED)) return RP_EIPV;
    result = command(4u, 0u, 1u);
    return result != RP_OK ? result : (read(STATUS) & RP_DAC_SPI_APPLIED) ? RP_OK : RP_EOP;
}
int rp_DacSpiWriteRaw(uint32_t frame) {
    if (frame > 0x7fffffu) return RP_EOOR; // bit 23 requests a read
    const std::lock_guard<std::mutex> lock(mutex);
    int result = prepare();
    if (result == RP_OK) result = writeChecked(TX, frame);
    return result == RP_OK ? command(8u, 1u, 0u) : result;
}
int rp_DacSpiReadRaw(uint32_t frame, uint32_t* response) {
    if (!response) return RP_UIA;
    if (frame > 0xffffffu || !(frame & 0x800000u)) return RP_EOOR;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = prepare();
    if (result != RP_OK) return result;
    const uint32_t period = read(PERIOD);
    // MISO needs the hardware's slower readback setting. Restore the write rate
    // after successful completion; leave it slow on timeout (no writes while busy).
    if (period < 16u) result = writeChecked(PERIOD, 16u);
    if (result == RP_OK) result = writeChecked(TX, frame);
    if (result == RP_OK) result = command(16u, 2u, 0u);
    if (result != RP_OK) return result;
    *response = read(RX);
    return period < 16u ? writeChecked(PERIOD, period) : RP_OK;
}
int rp_DacSpiGetCounters(uint32_t* frames, uint32_t* applies) {
    if (!frames || !applies) return RP_UIA;
    const std::lock_guard<std::mutex> lock(mutex);
    int result = checkMap();
    if (result == RP_OK) { *frames = read(FRAMES); *applies = read(APPLIES); }
    return result;
}
