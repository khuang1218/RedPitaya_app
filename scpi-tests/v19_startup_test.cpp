// Exercise the actual rp.cpp initialization/guards without real devices.
#include "rp.h"
#include "rp_hw-profiles.h"
#include "../rp-api/api/src/custom_hw.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <sys/mman.h>

static uint32_t memory[0x11000 / 4]{};
static unsigned hk_inits, gen_inits, ams_maps, daisy_inits, osc_inits, bnet_inits;
static unsigned forbidden_calls;
static bool fail_map;
int cmn_Init() { return RP_OK; }
int cmn_Release() { return RP_OK; }
int cmn_Map(size_t size, size_t offset, void** mapped) {
    if (offset == 0x400000) ++ams_maps;
    if (fail_map) { *mapped = MAP_FAILED; return RP_OK; }
    assert(size <= sizeof(memory)); *mapped = memory; return RP_OK;
}
int cmn_Unmap(size_t, void** mapped) { *mapped = nullptr; return RP_OK; }
int hk_Init() { ++hk_inits; return RP_OK; }
int hk_Release() { return RP_OK; }
int generate_Init() { ++gen_inits; return RP_OK; }
int generate_Release() { return RP_OK; }
int daisy_Init() { ++daisy_inits; return RP_OK; }
int daisy_Release() { return RP_OK; }
int osc_Init(int) { ++osc_inits; return RP_OK; }
int osc_Release() { return RP_OK; }
int bnet_Init() { ++bnet_inits; return RP_OK; }
int bnet_Release() { return RP_OK; }
int tdc_Release() { return RP_OK; }
int pulsegen_Release() { return RP_OK; }
int dacspi_Release() { return RP_OK; }
bool rp_HPIsFastDAC_PresentOrDefault() { return true; }
uint8_t rp_HPGetFastADCChannelsCountOrDefault() { return 2; }
int acq_Start(rp_channel_t) { ++forbidden_calls; return RP_OK; }
bool rp_HPGetIsDMAinv0_94OrDefault() { return true; }
int gen_axi_SetEnable(rp_channel_t, bool) { ++forbidden_calls; return RP_OK; }

int main() {
    uint32_t version = 0;
    assert(rp_GetCustomFpgaVersion(&version) == RP_EANI);
    memory[0x10000 / 4] = 0x54444313;
    assert(rp_InitAdresses() == RP_OK);
    assert(hk_inits == 1 && gen_inits == 1);
    assert(ams_maps == 0 && daisy_inits == 0 && osc_inits == 0 && bnet_inits == 0);
    assert(rp_GetCustomFpgaVersion(&version) == RP_OK && version == 19);
    assert(rp_AcqStart() == RP_EUF && forbidden_calls == 0);
    assert(rp_GenAxiSetEnable(RP_CH_1, true) == RP_EUF && forbidden_calls == 0);
    assert(rp_Release() == RP_OK && !customhw_IsV19());

    memory[0x10000 / 4] = 0x54444312;
    assert(rp_InitAdresses() == RP_OK);
    assert(rp_GetCustomFpgaVersion(&version) == RP_OK && version == 18);
    assert(ams_maps == 1 && daisy_inits == 1 && osc_inits == 1 && bnet_inits == 1);
    assert(rp_AcqStart() == RP_OK && forbidden_calls == 1);
    assert(rp_Release() == RP_OK);

    fail_map = true;
    assert(rp_InitAdresses() == RP_EMMD && rp_IsApiInit() == 0);
    assert(!customhw_IsV19());
    puts("PASS: actual API startup skips absent v19 engines, retains HK/ASG, blocks unsupported calls, preserves v18 startup and rejects failed mappings");
}
