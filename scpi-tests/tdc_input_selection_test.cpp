// Host regression: actual TDC API and SCPI handlers, memory-backed registers.
// Compile with the pinned libscpi sources and scpi-server/src/tdc.cpp.
// No physical FPGA access; HDL tests cover register side effects separately.
#include "../rp-api/api/src/tdc.cpp"
#include "../scpi-server/src/tdc.h"
#include "scpi/scpi.h"

#include <cassert>
#include <cstring>
#include <string>

static uint32_t registers[TDC_MAP_SIZE / sizeof(uint32_t)] = {};
static std::string response;
static int api_error = 0;

int cmn_Map(size_t size, size_t offset, void** mapped) {
    assert(size == TDC_MAP_SIZE && offset == TDC_UIO_SLOT_OFFSET);
    *mapped = registers;
    return RP_OK;
}
int cmn_Unmap(size_t, void**) { return RP_OK; }
const char* rp_GetError(int) { return "test error"; }
const char* getCmdName(scpi_t*) { return "TDC:INPUT"; }
bool getRetOnError() { return false; }
void requestSendNewLine(scpi_t*) {}
void rp_Log(scpi_t*, int, int error, const char*, ...) { api_error = error; }

static size_t capture(scpi_t*, const char* data, size_t size) {
    response.append(data, size);
    return size;
}
static scpi_result_t flush(scpi_t*) { return SCPI_RES_OK; }

int main() {
    uint32_t* hw = registers + TDC_SLOT_SUBOFFSET / sizeof(uint32_t);
    hw[TDC_ID_VERSION_OFFSET / 4] = 0x54444303;
    rp_tdc_input_t input = RP_TDC_INPUT_SINGLE;
    assert(rp_TdcGetInput(nullptr) == RP_UIA);
    assert(rp_TdcSetInput((rp_tdc_input_t)2) == RP_EOOR);
    assert(rp_TdcSetInput(RP_TDC_INPUT_SINGLE) == RP_EUF);
    assert(rp_TdcGetInput(&input) == RP_EUF);
    assert(hw[TDC_INPUT_SELECT_OFFSET / 4] == 0);
    hw[TDC_ID_VERSION_OFFSET / 4] = 0x54444304;
    assert(rp_TdcGetInput(&input) == RP_OK && input == RP_TDC_INPUT_LVDS);
    hw[TDC_CONTROL_OFFSET / 4] = TDC_CTRL_ENABLE;
    assert(rp_TdcSetInput(RP_TDC_INPUT_SINGLE) == RP_EIPV);
    hw[TDC_CONTROL_OFFSET / 4] = 0;
    hw[TDC_STATUS_OFFSET / 4] = RP_TDC_STATUS_BUSY;
    assert(rp_TdcSetInput(RP_TDC_INPUT_SINGLE) == RP_EIPV);
    hw[TDC_STATUS_OFFSET / 4] = 0;
    assert(rp_TdcSetInput(RP_TDC_INPUT_SINGLE) == RP_OK);
    assert(rp_TdcGetInput(&input) == RP_OK && input == RP_TDC_INPUT_SINGLE);

    const scpi_command_t commands[] = {
        {"TDC:INPut", RP_TdcInput}, {"TDC:INPut?", RP_TdcInputQ},
        SCPI_CMD_LIST_END
    };
    scpi_interface_t interface = {};
    interface.write = capture;
    interface.flush = flush;
    char buffer[256];
    scpi_error_t errors[16];
    scpi_t context;
    SCPI_Init(&context, commands, &interface, scpi_units_def,
              "test", "tdc", "0", "0", buffer, sizeof(buffer), errors, 16);
    auto send = [&](const char* command) {
        response.clear(); api_error = 0;
        SCPI_Input(&context, command, (int)strlen(command));
    };
    send("TDC:INPUT LVDS\n");
    assert(api_error == 0 && hw[TDC_INPUT_SELECT_OFFSET / 4] == 0);
    send("TDC:INPUT?\n"); assert(response == "LVDS\r\n");
    send("tdc:inp single\n");
    assert(api_error == 0 && hw[TDC_INPUT_SELECT_OFFSET / 4] == 1);
    send("TDC:INP?\n"); assert(response == "SINGLE\r\n");
    send("TDC:INPUT INVALID\n");
    assert(api_error != 0 && hw[TDC_INPUT_SELECT_OFFSET / 4] == 1);
    SCPI_ErrorClear(&context);
    send("TDC:INPUT\n"); assert(api_error != 0);
    SCPI_ErrorClear(&context);
    hw[TDC_CONTROL_OFFSET / 4] = TDC_CTRL_ENABLE;
    send("TDC:INPUT LVDS\n");
    assert(api_error == RP_EIPV && hw[TDC_INPUT_SELECT_OFFSET / 4] == 1);
    hw[TDC_CONTROL_OFFSET / 4] = 0;
    hw[TDC_ID_VERSION_OFFSET / 4] = 0x54444303;
    send("TDC:INPUT LVDS\n");
    assert(api_error == RP_EUF && hw[TDC_INPUT_SELECT_OFFSET / 4] == 1);
    tdc_Release();
    puts("PASS: TDC input API/version/busy guards and SCPI set/query/invalid commands");
}
