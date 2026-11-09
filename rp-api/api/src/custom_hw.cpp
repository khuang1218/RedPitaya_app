#include "custom_hw.h"
#include "common.h"
#include "rp.h"

#include <atomic>
#include <sys/mman.h>

namespace {
std::atomic<uint32_t> fpga_version{0};
}

int customhw_Init() {
    void* mapping = nullptr;
    constexpr uint32_t size = 0x11000u;
    int result = cmn_Map(size, 0x00700000u, &mapping);
    if (result != RP_OK) return result;
    if (mapping == MAP_FAILED || mapping == nullptr) return RP_EMMD;
    auto* registers = reinterpret_cast<volatile uint32_t*>(static_cast<uint8_t*>(mapping) + 0x10000u);
    uint32_t id = 0;
    for (unsigned i = 0; i < 16; ++i) id = registers[0];
    result = cmn_Unmap(size, &mapping);
    if (result == RP_OK) fpga_version = (id & 0xffffff00u) == 0x54444300u ? id & 0xffu : 0u;
    return result;
}

void customhw_Release() { fpga_version = 0; }
bool customhw_IsV19() { return fpga_version == 19u; }

int rp_GetCustomFpgaVersion(uint32_t* version) {
    if (!version) return RP_UIA;
    if (!rp_IsApiInit()) return RP_EANI;
    *version = fpga_version;
    return RP_OK;
}
