// Host regression: actual TDC API and SCPI handlers, memory-backed registers.
// Compile with the pinned libscpi sources and scpi-server/src/tdc.cpp.
// No physical FPGA access; HDL tests cover register side effects separately.
#include "../rp-api/api/src/tdc.cpp"
#include "../scpi-server/src/tdc.h"
#include "scpi/scpi.h"

#include <cassert>
#include <cstdlib>
#include <cstring>
#include <string>

// Report failed host assertions without opening a Windows runtime dialog.
#undef assert
#define assert(condition) do { if (!(condition)) { \
    fprintf(stderr,"Assertion failed at line %d: %s\n",__LINE__,#condition); \
    std::exit(1); } } while (0)

static uint32_t registers[TDC_MAP_SIZE / sizeof(uint32_t)] = {};
static std::string response;
static int api_error = 0;
static uint64_t test_period=1000, test_high=500;
static bool test_pulse_enabled=true;
int rp_PulseGetEnabled(bool* enabled) { *enabled=test_pulse_enabled; return RP_OK; }
int rp_PulseGetTiming(uint64_t* period, uint64_t* high) {
    *period=test_period; *high=test_high; return RP_OK;
}

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
        {"TDC:WIDTh:ARM", RP_TdcWidthArm},
        {"TDC:WIDTh:STATus?", RP_TdcWidthStatusQ},
        {"TDC:WIDTh:COUNt?", RP_TdcWidthCountQ},
        {"TDC:WIDTh:CAPacity?", RP_TdcWidthCapacityQ},
        {"TDC:WIDTh:TICK?", RP_TdcWidthTickQ},
        {"TDC:WIDTh:DATA?", RP_TdcWidthDataQ},
        {"TDC:WIDTh:CALibration:ACTivate", RP_TdcWidthCalibration},
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
    assert(rp_TdcWidthArm(1)==RP_EUF);
    hw[TDC_ID_VERSION_OFFSET/4]=0x54444305;
    assert(rp_TdcWidthArm(1)==RP_EUF); // missing optional block signature
    hw[TDC_WIDTH_ID/4]=0x50574201;
    hw[TDC_WIDTH_CAPACITY/4]=1024; hw[TDC_WIDTH_MIN_PERIOD/4]=1000;
    hw[TDC_NUM_TAPS_OFFSET/4]=512;
    assert(rp_TdcWidthArm(0)==RP_EOOR && rp_TdcWidthArm(1025)==RP_EOOR);
    test_period=8;test_high=4;assert(rp_TdcWidthArm(1)==RP_EOOR);
    test_period=1000;test_high=400;assert(rp_TdcWidthArm(1)==RP_EOOR);
    test_high=500;
    test_pulse_enabled=false;assert(rp_TdcWidthArm(1)==RP_EIPV);test_pulse_enabled=true;
    hw[TDC_CONTROL_OFFSET/4]=TDC_CTRL_INTERNAL_TEST;
    assert(rp_TdcWidthArm(1)==RP_EIPV);hw[TDC_CONTROL_OFFSET/4]=0;
    hw[TDC_WIDTH_STATUS/4]=RP_TDC_WIDTH_BUSY;
    assert(rp_TdcWidthArm(1)==RP_EIPV);
    hw[TDC_WIDTH_STATUS/4]=0;
    assert(rp_TdcWidthArm(16)==RP_OK && hw[TDC_WIDTH_COMMAND/4]==1);
    assert(hw[TDC_WIDTH_REQUEST_COUNT/4]==16 && hw[TDC_WIDTH_TIMEOUT/4]==532);
    hw[TDC_WIDTH_STATUS/4]=RP_TDC_WIDTH_DONE;hw[TDC_WIDTH_COUNT/4]=1;
    hw[TDC_WIDTH_RECORD/4]=1;hw[(TDC_WIDTH_RECORD+4)/4]=257;
    hw[(TDC_WIDTH_RECORD+8)/4]=25;hw[(TDC_WIDTH_RECORD+12)/4]=(6u<<16)|2u;
    hw[TDC_WIDTH_PS/4]=100000;hw[TDC_WIDTH_TICK/4]=4000;
    rp_tdc_width_result_t record;
    assert(rp_TdcWidthRead(0,&record,1)==RP_OK);
    assert(record.cycle_id==1 && record.flags==257 && record.coarse_ticks==25 &&
           record.rise_raw==2 && record.fall_raw==6 && record.width_ps==100000);
    assert(rp_TdcWidthRead(1,&record,1)==RP_EOOR);
    assert(rp_TdcWidthRead(0,nullptr,1)==RP_UIA);
    assert(rp_TdcWidthWriteLut(false,512,nullptr,1)==RP_UIA);
    uint16_t lut=100;
    assert(rp_TdcWidthWriteLut(false,512,&lut,1)==RP_EOOR);
    assert(rp_TdcWidthActivateCalibration(true)==RP_EIPV);
    send("TDC:WIDTH:DATA? 0,1\n");assert(response=="1,257,25,2,6,100000\r\n");
    send("TDC:WIDT:CAP?\n");assert(response=="1024\r\n");
    send("TDC:WIDTH:TICK?\n");assert(response=="4000\r\n");
    send("TDC:WIDTH:ARM 0\n");assert(api_error==RP_EOOR);
    send("TDC:WIDTH:DATA? 0,129\n");assert(api_error==RP_EOOR);
    send("TDC:WIDTH:ARM 4\n");assert(api_error==0 && hw[TDC_WIDTH_REQUEST_COUNT/4]==4);
    // v6 enlarges hardware capacity without changing the record-register ABI.
    hw[TDC_ID_VERSION_OFFSET/4]=0x54444306;
    hw[TDC_WIDTH_CAPACITY/4]=16384;
    assert(rp_TdcWidthArm(16385)==RP_EOOR);
    send("TDC:WIDTH:ARM 16384\n");
    assert(api_error==0 && hw[TDC_WIDTH_REQUEST_COUNT/4]==16384);
    send("TDC:WIDTH:CAPACITY?\n");assert(response=="16384\r\n");
    hw[TDC_WIDTH_COUNT/4]=16384;hw[TDC_WIDTH_RECORD/4]=16384;
    assert(rp_TdcWidthRead(16383,&record,1)==RP_OK && record.cycle_id==16384);
    assert(hw[TDC_WIDTH_INDEX/4]==16383);
    assert(rp_TdcWidthRead(16384,&record,1)==RP_EOOR);
    hw[TDC_ID_VERSION_OFFSET/4]=0x54444307; // reduced storage preserves PWB v1
    uint32_t width_capacity=0;
    assert(rp_TdcWidthGetCapacity(&width_capacity)==RP_OK && width_capacity==16384);
    hw[TDC_WIDTH_STATUS/4]=RP_TDC_WIDTH_DONE|RP_TDC_WIDTH_OVERFLOW;
    uint32_t width_status=0;
    assert(rp_TdcWidthGetStatus(&width_status)==RP_OK && (width_status&RP_TDC_WIDTH_OVERFLOW));
    tdc_Release();
    puts("PASS: TDC input and width API/SCPI; v5/v6/v7 compatibility, 16384 ARM/last-record read, overflow, busy/rate/duty guards and parameter errors");
}
