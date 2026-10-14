#include "pulsegen.h"
#include "common.h"
#include "rp.h"
#include <cstdio>

static scpi_result_t pulse_result(scpi_t* context, int result, bool query = false) {
    if (result == RP_OK) return SCPI_RES_OK;
    RP_LOG_CRIT("Pulse generator: %s", rp_GetError(result));
    if (query && getRetOnError()) requestSendNewLine(context);
    return SCPI_RES_ERR;
}

scpi_result_t RP_PulseReset(scpi_t* context) {
    return pulse_result(context, rp_PulseReset());
}

scpi_result_t RP_PulseTiming(scpi_t* context) {
    uint64_t period_ns = 0, high_ns = 0;
    if (!SCPI_ParamUInt64(context, &period_ns, true) ||
        !SCPI_ParamUInt64(context, &high_ns, true)) return SCPI_RES_ERR;
    return pulse_result(context, rp_PulseSetTiming(period_ns, high_ns));
}

scpi_result_t RP_PulseTimingQ(scpi_t* context) {
    uint64_t period_ns = 0, high_ns = 0;
    int result = rp_PulseGetTiming(&period_ns, &high_ns);
    if (pulse_result(context, result, true) != SCPI_RES_OK) return SCPI_RES_ERR;
    SCPI_ResultUInt64(context, period_ns);
    SCPI_ResultUInt64(context, high_ns);
    return SCPI_RES_OK;
}

scpi_result_t RP_PulsePeriodQ(scpi_t* context) {
    uint64_t period_ns = 0, high_ns = 0;
    int result = rp_PulseGetTiming(&period_ns, &high_ns);
    if (pulse_result(context, result, true) != SCPI_RES_OK) return SCPI_RES_ERR;
    SCPI_ResultUInt64(context, period_ns);
    return SCPI_RES_OK;
}

scpi_result_t RP_PulsePeriod(scpi_t* context) {
    uint64_t period_ns = 0;
    if (!SCPI_ParamUInt64(context, &period_ns, true)) return SCPI_RES_ERR;
    return pulse_result(context, rp_PulseSetPeriod(period_ns));
}

scpi_result_t RP_PulseWidth(scpi_t* context) {
    uint64_t high_ns = 0;
    if (!SCPI_ParamUInt64(context, &high_ns, true)) return SCPI_RES_ERR;
    return pulse_result(context, rp_PulseSetHighTime(high_ns));
}

scpi_result_t RP_PulseWidthQ(scpi_t* context) {
    uint64_t period_ns = 0, high_ns = 0;
    int result = rp_PulseGetTiming(&period_ns, &high_ns);
    if (pulse_result(context, result, true) != SCPI_RES_OK) return SCPI_RES_ERR;
    SCPI_ResultUInt64(context, high_ns);
    return SCPI_RES_OK;
}

scpi_result_t RP_PulseFrequency(scpi_t* context) {
    double frequency_hz = 0;
    if (!SCPI_ParamDouble(context, &frequency_hz, true)) return SCPI_RES_ERR;
    return pulse_result(context, rp_PulseSetFrequency(frequency_hz));
}

scpi_result_t RP_PulseFrequencyQ(scpi_t* context) {
    double frequency_hz = 0;
    int result = rp_PulseGetFrequency(&frequency_hz);
    if (pulse_result(context, result, true) != SCPI_RES_OK) return SCPI_RES_ERR;
    SCPI_ResultDouble(context, frequency_hz);
    return SCPI_RES_OK;
}

scpi_result_t RP_PulseOutput(scpi_t* context) {
    scpi_bool_t enable = FALSE;
    if (!SCPI_ParamBool(context, &enable, true)) return SCPI_RES_ERR;
    return pulse_result(context, rp_PulseSetEnabled(enable));
}

scpi_result_t RP_PulseOutputQ(scpi_t* context) {
    bool enable = false;
    int result = rp_PulseGetEnabled(&enable);
    if (pulse_result(context, result, true) != SCPI_RES_OK) return SCPI_RES_ERR;
    SCPI_ResultBool(context, enable);
    return SCPI_RES_OK;
}

scpi_result_t RP_PulseStatusQ(scpi_t* context) {
    uint32_t status = 0;
    int result = rp_PulseGetStatus(&status);
    if (pulse_result(context, result, true) != SCPI_RES_OK) return SCPI_RES_ERR;
    SCPI_ResultUInt32Base(context, status, 10);
    return SCPI_RES_OK;
}

scpi_result_t RP_PulsePinQ(scpi_t* context) {
    rp_dpin_t pin = RP_DIO0_P;
    int result = rp_PulseGetPin(&pin);
    if (pulse_result(context, result, true) != SCPI_RES_OK) return SCPI_RES_ERR;
    char name[16];
    std::snprintf(name, sizeof(name), "DIO%u_P", static_cast<unsigned>(pin) - RP_DIO0_P);
    SCPI_ResultMnemonic(context, name);
    return SCPI_RES_OK;
}
