// Actual API and libscpi handlers against an independent memory-backed model.
// No /dev/uio, /dev/mem, board connection, or physical DAC is used.
#include "rp.h"
#include "scpi/scpi.h"
#include "scpi/units.h"
#include "../scpi-server/src/scpi-commands.h"
#include "../rp-api/api/src/tdc.h"
#include "../rp-api/api/src/pulsegen.h"
#include "../rp-api/api/src/dac_spi.h"
#include "../rp-api/api/src/custom_hw.h"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

static uint32_t memory[0x41000 / 4]{};
static uint16_t luts[2][1024]{};
static uint16_t loaded[4]{};
static std::string output;
static int logged_error = 0;
static bool drop_command = false, wrong_counter = false, drop_config = false;
static uint32_t read_period = 0, dac_commands = 0;
static unsigned second_maps = 0;
static uint32_t* block(unsigned offset) { return memory + offset / 4; }

int cmn_Map(size_t size, size_t offset, void** mapped) {
    assert(offset == 0x700000 && size <= sizeof(memory));
    if (size == 0x31000) ++second_maps;
    *mapped = memory;
    return RP_OK;
}
int cmn_Unmap(size_t, void** mapped) { *mapped = nullptr; return RP_OK; }
int rp_IsApiInit() { return 1; }
const char* rp_GetError(int) { return "test error"; }
const char* rp_GetVersion() { return "v19 host regression"; }
const char* getCmdName(scpi_t*) { return "v19 test"; }
bool getRetOnError() { return false; }
void requestSendNewLine(scpi_t*) {}
void rp_Log(scpi_t*, int, int error, const char*, ...) { logged_error = error; }

uint32_t custom_mmio_Read(volatile uint32_t* address) {
    const size_t byte = (address - memory) * 4;
    for (unsigned ch = 0; ch < 2; ++ch) {
        const size_t base = ch ? 0x30000 : 0x10000;
        if (byte == base + 0x13c) return luts[ch][block(base)[0x138 / 4]];
    }
    return *address;
}
void custom_mmio_Write(volatile uint32_t* address, uint32_t value) {
    const size_t byte = (address - memory) * 4;
    if (byte == 0x4000c && drop_config) return;
    *address = value;
    for (unsigned ch = 0; ch < 2; ++ch) {
        const size_t base = ch ? 0x30000 : 0x10000;
        auto* t = block(base);
        if (byte == base + 0x13c) luts[ch][t[0x138 / 4]] = value;
        if (byte == base + 0x118) {
            t[0x11c / 4] = value + 1;
            t[0x120 / 4] = RP_TDC_WIDTH_VALID | RP_TDC_WIDTH_COARSE_ONLY | (1u << 16) | (1u << 24);
            t[0x124 / 4] = ch ? 50 : 25;
            t[0x128 / 4] = (6u << 16) | 5u;
            t[0x134 / 4] = ch ? 200000 : 100000;
        }
    }
    if (byte == 0x20014) {
        auto* p = block(0x20000);
        if (value == 1) {
            p[0x20 / 4] = p[0x0c / 4]; p[0x24 / 4] = p[0x10 / 4];
            p[0x08 / 4] = RP_PULSE_STATUS_READY | (p[0x04 / 4] ? RP_PULSE_STATUS_ENABLED | RP_PULSE_STATUS_CLAIMED : 0);
        } else if (value == 2) p[0x08 / 4] = RP_PULSE_STATUS_READY;
    }
    if (byte == 0x40004) {
        auto* d = block(0x40000);
        if (value == 32) { d[2] &= ~RP_DAC_SPI_DONE; return; }
        ++dac_commands;
        if (drop_command) return;
        if (value == 1 || value == 2) {
            for (unsigned i = 0; i < 4; ++i) loaded[i] = d[4 + i];
            d[2] |= RP_DAC_SPI_LOADED;
            d[0x2c / 4] += wrong_counter ? 3 : 4;
        }
        if (value == 1 || value == 4) {
            for (unsigned i = 0; i < 4; ++i) d[0x40 / 4 + i] = loaded[i];
            d[2] |= RP_DAC_SPI_APPLIED; ++d[0x28 / 4];
        }
        if (value == 8) { ++d[0x2c / 4]; d[2] &= ~(RP_DAC_SPI_LOADED | RP_DAC_SPI_APPLIED); }
        if (value == 16) {
            read_period = d[3];
            assert(read_period >= 16);
            d[0x24 / 4] = 0xcafe; d[0x2c / 4] += 2;
        }
        d[2] |= RP_DAC_SPI_DONE;
    }
}

static size_t capture(scpi_t*, const char* data, size_t n) { output.append(data, n); return n; }
static scpi_result_t flush(scpi_t*) { return SCPI_RES_OK; }

int main() {
    for (const unsigned base : {0x10000u, 0x30000u}) {
        auto* t = block(base);
        t[0] = 0x54444313; t[0x18 / 4] = 512;
        t[0x100 / 4] = 0x50574201; t[0x110 / 4] = 16384;
        t[0x114 / 4] = 16384; t[0x12c / 4] = 4000;
        t[0x144 / 4] = 40; t[0x148 / 4] = 1; t[0x15c / 4] = 0x46524d01;
        t[0x160 / 4] = 0x44424701; t[0x164 / 4] = 64;
    }
    auto* p = block(0x20000);
    p[0] = 0x50554c01; p[2] = RP_PULSE_STATUS_READY; p[0x18 / 4] = 2; p[0x1c / 4] = 1;
    p[0x20 / 4] = 5000; p[0x24 / 4] = 2500;
    auto* d = block(0x40000);
    d[0] = 0x44414301; d[2] = RP_DAC_SPI_READY; d[3] = 12;
    d[0x30 / 4] = 125000000; d[0x34 / 4] = 16;
    assert(customhw_Init() == RP_OK);

    // Explicit channel selection, default alias, independent input/offset/LUT/RAM.
    assert(rp_TdcSetInputCh(RP_CH_1, RP_TDC_INPUT_SINGLE) == RP_OK);
    assert(rp_TdcSetInputCh(RP_CH_2, RP_TDC_INPUT_LVDS) == RP_OK);
    rp_tdc_input_t input;
    assert(rp_TdcGetInput(&input) == RP_OK && input == RP_TDC_INPUT_SINGLE);
    assert(rp_TdcGetInputCh(RP_CH_2, &input) == RP_OK && input == RP_TDC_INPUT_LVDS);
    assert(rp_TdcWidthSetFrameOffsetCh(RP_CH_1, 4) == RP_OK);
    assert(rp_TdcWidthSetFrameOffsetCh(RP_CH_2, 12) == RP_OK);
    uint32_t offset = 0;
    assert(rp_TdcWidthGetFrameOffset(&offset) == RP_OK && offset == 4);
    uint16_t a[2] = {123, 456}, b[2] = {789, 1000}, got[2]{};
    assert(rp_TdcWidthWriteLutCh(RP_CH_1, false, 5, a, 2) == RP_OK);
    assert(rp_TdcWidthWriteLutCh(RP_CH_2, false, 5, b, 2) == RP_OK);
    assert(rp_TdcWidthReadLutCh(RP_CH_1, false, 5, got, 2) == RP_OK && got[0] == 123);
    assert(rp_TdcWidthReadLutCh(RP_CH_2, false, 5, got, 2) == RP_OK && got[1] == 1000);
    rp_tdc_width_result_t records[2];
    assert(rp_TdcWidthReadCh(RP_CH_1, 16382, records, 2) == RP_OK && records[1].cycle_id == 16384 && records[1].width_ps == 100000);
    assert(rp_TdcWidthReadCh(RP_CH_2, 0, records, 2) == RP_OK && records[1].width_ps == 200000);
    assert(rp_TdcWidthArmCh(RP_CH_3, 1) == RP_EOOR);
    // Two callers may interleave complete indexed transactions without sharing state.
    std::thread first([&] { for (int i = 0; i < 100; ++i) assert(rp_TdcWidthWriteLutCh(RP_CH_1, false, 5, a, 2) == RP_OK); });
    std::thread second([&] { for (int i = 0; i < 100; ++i) assert(rp_TdcWidthWriteLutCh(RP_CH_2, false, 5, b, 2) == RP_OK); });
    first.join(); second.join();

    assert(rp_PulseSetTiming(10000, 3000) == RP_OK);
    assert(rp_PulseSetDutyCycle(27.33) == RP_OK);
    double duty = 0, hz = 0;
    assert(rp_PulseGetDutyCycle(&duty) == RP_OK && std::abs(duty - 27.34) < 1e-8);
    assert(rp_PulseSetFrequency(200000) == RP_OK);
    uint64_t period = 0, high = 0;
    assert(rp_PulseGetTiming(&period, &high) == RP_OK && period == 5000 && high == 1368);
    assert(rp_PulseSetEnabled(true) == RP_OK);
    assert(rp_PulseSetHighTime(1000) == RP_EOP);
    assert(rp_TdcWidthArmCh(RP_CH_1, 16384) == RP_OK);
    assert(rp_TdcWidthArmCh(RP_CH_2, 16384) == RP_OK);
    assert(block(0x10000)[0x10c / 4] == 16384 && block(0x30000)[0x10c / 4] == 16384);
    p[0x24 / 4] = 3; assert(rp_TdcWidthArm(1) == RP_EOOR); // HIGH <8 ns
    p[0x24 / 4] = p[0x20 / 4] - 3; assert(rp_TdcWidthArm(1) == RP_EOOR);
    p[0x20 / 4] = 18; p[0x24 / 4] = 9; assert(rp_TdcWidthArm(1) == RP_EOOR);
    assert(rp_PulseSetEnabled(false) == RP_OK);
    assert(rp_PulseSetTiming(40, 8) == RP_OK && rp_PulseSetEnabled(true) == RP_OK);
    assert(rp_TdcWidthArm(1) == RP_OK); // 20% drive at minimum frame period

    uint16_t weights[4] = {0, 12345, 32768, 65535}, values[4]{};
    assert(rp_DacSpiApply() == RP_EIPV);
    assert(rp_DacSpiSetWeights(weights, false) == RP_OK);
    assert(!(d[2] & RP_DAC_SPI_APPLIED));
    assert(rp_DacSpiGetWeights(values, true) == RP_EIPV);
    assert(rp_DacSpiApply() == RP_OK);
    assert(rp_DacSpiGetWeights(values, true) == RP_OK && !std::memcmp(values, weights, sizeof(values)));
    weights[0] = 500;
    assert(rp_DacSpiSetWeights(weights, true) == RP_OK && d[0x40 / 4] == 500);
    assert(rp_DacSpiSetFrequency(25000000) == RP_OK && d[3] == 5);
    assert(rp_DacSpiReadRaw(0x900000, &offset) == RP_OK && offset == 0xcafe && read_period == 16 && d[3] == 5);
    assert(rp_DacSpiGetFrequency(&hz) == RP_OK && hz == 25000000);
    assert(rp_DacSpiWriteRaw(0x010004) == RP_OK);
    assert(rp_DacSpiApply() == RP_EIPV && rp_DacSpiGetWeights(values, true) == RP_EIPV);
    const auto commands_before = dac_commands;
    assert(rp_DacSpiWriteRaw(0x800000) == RP_EOOR);
    assert(rp_DacSpiReadRaw(0x100000, &offset) == RP_EOOR);
    assert(rp_DacSpiSetPeriod(3) == RP_EOOR && rp_DacSpiSetPeriod(251) == RP_EOOR);
    assert(rp_DacSpiSetLdacWidth(12) == RP_EOOR);
    assert(rp_DacSpiSetWeights(nullptr, true) == RP_UIA && dac_commands == commands_before);
    drop_config = true; assert(rp_DacSpiSetPeriod(6) == RP_EOP); drop_config = false;
    wrong_counter = true; assert(rp_DacSpiSetWeights(weights, true) == RP_EOP); wrong_counter = false;
    drop_command = true; assert(rp_DacSpiSetWeights(weights, true) == RP_EOP); drop_command = false;
    d[2] |= RP_DAC_SPI_BUSY;
    const auto busy_before = dac_commands;
    assert(rp_DacSpiSetWeights(weights, true) == RP_EOP && dac_commands == busy_before);
    assert(rp_DacSpiGetWeights(values, true) == RP_EOP);
    d[2] = RP_DAC_SPI_READY;
    d[0x2c / 4] = 0xfffffffe; d[0x28 / 4] = 0xffffffff;
    assert(rp_DacSpiSetWeights(weights, true) == RP_OK && d[0x2c / 4] == 2 && d[0x28 / 4] == 0);

    // Dispatch the actual production command table and actual pinned parser.
    const auto* commands = rp_scpi_CommandsForVersion(19);
    bool saw_tdc = false, saw_asg = false;
    for (auto* c = commands; c->pattern; ++c) {
        assert(std::strncmp(c->pattern, "ACQ:", 4) && std::strncmp(c->pattern, "BNET:", 5));
        assert(std::strncmp(c->pattern, "ANALOG:", 7) && std::strncmp(c->pattern, "DAISY:", 6));
        assert(std::strncmp(c->pattern, "LCR:", 4) && !std::strstr(c->pattern, ":AXI:"));
        saw_tdc |= std::strncmp(c->pattern, "TDC#:", 5) == 0;
        saw_asg |= std::strcmp(c->pattern, "SOUR#:FREQ:FIX") == 0;
    }
    assert(saw_tdc && saw_asg);
    scpi_interface_t interface{}; interface.write = capture; interface.flush = flush;
    char buffer[4096]; scpi_error_t errors[32]; scpi_t context;
    SCPI_Init(&context, commands, &interface, scpi_units_def, "test", "v19", "0", "0", buffer, sizeof(buffer), errors, 32);
    auto send = [&](const char* text) {
        output.clear(); logged_error = 0; SCPI_ErrorClear(&context);
        SCPI_Input(&context, text, std::strlen(text));
    };
    send("TDC:WIDTH:OFFSET?\n"); assert(output == "4\r\n");
    send("TDC1:WIDTH:OFFSET?\n"); assert(output == "4\r\n");
    send("TDC2:WIDTH:OFFSET?\n"); assert(output == "12\r\n");
    send("tdc2:widt:offs?\n"); assert(output == "12\r\n");
    send("TDC2:WIDTH:OFFSET 16\n"); assert(logged_error == 0 && block(0x30000)[0x158 / 4] == 16);
    send("TDC2:WIDTH:ARM 10\n"); assert(logged_error == 0 && block(0x30000)[0x10c / 4] == 10);
    send("TDC3:WIDTH:ARM 10\n"); assert(logged_error == RP_EOOR);
    send("TDC0:WIDTH:ARM 10\n"); assert(logged_error == RP_EOOR);
    send("DAC:WEIGHTS 0,100,200,65535\n"); assert(logged_error == 0 && d[0x44 / 4] == 100);
    send("DAC:APPLIED?\n"); assert(output == "0,100,200,65535\r\n");
    const auto before_bad = dac_commands;
    send("DAC:WEIGHTS 0,1,2,65536\n"); assert(dac_commands == before_bad && SCPI_ErrorCount(&context));
    send("DAC:WEIGHTS 0,1\n"); assert(dac_commands == before_bad && SCPI_ErrorCount(&context));
    send("DAC:WEIGHTS 0,1,2,3,4\n"); assert(dac_commands == before_bad && SCPI_ErrorCount(&context));
    send("DAC:SPI:RAW:READ? #H900000\n"); assert(output == "51966\r\n");
    send("PULSE:OUTPUT OFF\n");
    send("PULSE:TIMING 10000,2000\n"); assert(logged_error == 0);
    send("PULSE:DCYCLE 31.25\n"); assert(logged_error == 0);
    send("PULSE:TIMING?\n"); assert(output == "10000,3126\r\n");
    send("SYST:FPGA:VERS?\n"); assert(output == "19\r\n");

    // No second-core or SPI-slot access on the older qualified image.
    assert(tdc_Release() == RP_OK && dacspi_Release() == RP_OK);
    block(0x10000)[0] = 0x54444312;
    const auto prior_maps = second_maps;
    assert(rp_TdcWidthGetVersionCh(RP_CH_2, &offset) == RP_EUF && second_maps == prior_maps);
    assert(rp_DacSpiSetWeights(weights, true) == RP_EUF);
    assert(rp_TdcWidthGetVersion(&offset) == RP_OK && offset == 18);
    assert(tdc_Release() == RP_OK && pulsegen_Release() == RP_OK);
    puts("PASS: dual TDC isolation/readout/concurrency, unequal duty and timing guards, DAC load/LDAC/raw read/counter/readback/timeout, actual SCPI dispatch and v18 fallback");
}
