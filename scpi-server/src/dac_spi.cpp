#include "dac_spi.h"
#include "common.h"
#include "rp.h"

namespace {
scpi_result_t result(scpi_t* context, int code, bool query = false) {
    if (code == RP_OK) return SCPI_RES_OK;
    SCPI_ErrorPush(context, code == RP_EOOR ? SCPI_ERROR_DATA_OUT_OF_RANGE : SCPI_ERROR_EXECUTION_ERROR);
    rp_Log(context, LOG_CRIT, code, "FPGA DAC SPI: %s", rp_GetError(code));
    if (query && getRetOnError()) requestSendNewLine(context);
    return SCPI_RES_ERR;
}
bool endOfParameters(scpi_t* context) {
    scpi_parameter_t extra;
    if (!SCPI_Parameter(context, &extra, false)) return true;
    SCPI_ErrorPush(context, SCPI_ERROR_PARAMETER_NOT_ALLOWED);
    return false;
}
scpi_result_t getU32(scpi_t* context, int (*get)(uint32_t*)) {
    uint32_t value = 0;
    if (result(context, get(&value), true) != SCPI_RES_OK) return SCPI_RES_ERR;
    SCPI_ResultUInt32(context, value);
    return SCPI_RES_OK;
}
scpi_result_t setU32(scpi_t* context, int (*set)(uint32_t)) {
    uint32_t value = 0;
    if (!SCPI_ParamUInt32(context, &value, true)) return SCPI_RES_ERR;
    if (!endOfParameters(context)) return SCPI_RES_ERR;
    return result(context, set(value));
}
scpi_result_t weights(scpi_t* context, bool apply) {
    uint16_t codes[4];
    for (unsigned i = 0; i < 4; ++i) {
        uint32_t value = 0;
        if (!SCPI_ParamUInt32(context, &value, true)) return SCPI_RES_ERR;
        if (value > UINT16_MAX) return result(context, RP_EOOR);
        codes[i] = static_cast<uint16_t>(value);
    }
    if (!endOfParameters(context)) return SCPI_RES_ERR;
    return result(context, rp_DacSpiSetWeights(codes, apply));
}
scpi_result_t weightsQuery(scpi_t* context, bool applied) {
    uint16_t codes[4] = {};
    if (result(context, rp_DacSpiGetWeights(codes, applied), true) != SCPI_RES_OK) return SCPI_RES_ERR;
    for (const auto code : codes) SCPI_ResultUInt32(context, code);
    return SCPI_RES_OK;
}
} // namespace
scpi_result_t RP_DacSpiStatusQ(scpi_t* c) { return getU32(c, rp_DacSpiGetStatus); }
scpi_result_t RP_DacSpiPeriod(scpi_t* c) { return setU32(c, rp_DacSpiSetPeriod); }
scpi_result_t RP_DacSpiPeriodQ(scpi_t* c) { return getU32(c, rp_DacSpiGetPeriod); }
scpi_result_t RP_DacSpiLdacWidth(scpi_t* c) { return setU32(c, rp_DacSpiSetLdacWidth); }
scpi_result_t RP_DacSpiLdacWidthQ(scpi_t* c) { return getU32(c, rp_DacSpiGetLdacWidth); }
scpi_result_t RP_DacSpiWeights(scpi_t* c) { return weights(c, true); }
scpi_result_t RP_DacSpiLoad(scpi_t* c) { return weights(c, false); }
scpi_result_t RP_DacSpiWeightsQ(scpi_t* c) { return weightsQuery(c, false); }
scpi_result_t RP_DacSpiAppliedQ(scpi_t* c) { return weightsQuery(c, true); }
scpi_result_t RP_DacSpiApply(scpi_t* c) { return result(c, rp_DacSpiApply()); }
scpi_result_t RP_DacSpiFrequency(scpi_t* c) {
    double hz = 0;
    if (!SCPI_ParamDouble(c, &hz, true)) return SCPI_RES_ERR;
    if (!endOfParameters(c)) return SCPI_RES_ERR;
    return result(c, rp_DacSpiSetFrequency(hz));
}
scpi_result_t RP_DacSpiFrequencyQ(scpi_t* c) {
    double hz = 0;
    if (result(c, rp_DacSpiGetFrequency(&hz), true) != SCPI_RES_OK) return SCPI_RES_ERR;
    SCPI_ResultDouble(c, hz);
    return SCPI_RES_OK;
}
scpi_result_t RP_DacSpiRawWrite(scpi_t* c) {
    uint32_t frame = 0;
    if (!SCPI_ParamUInt32(c, &frame, true)) return SCPI_RES_ERR;
    if (!endOfParameters(c)) return SCPI_RES_ERR;
    return result(c, rp_DacSpiWriteRaw(frame));
}
scpi_result_t RP_DacSpiRawReadQ(scpi_t* c) {
    uint32_t frame = 0, response = 0;
    if (!SCPI_ParamUInt32(c, &frame, true)) return SCPI_RES_ERR;
    if (!endOfParameters(c)) return SCPI_RES_ERR;
    if (result(c, rp_DacSpiReadRaw(frame, &response), true) != SCPI_RES_OK) return SCPI_RES_ERR;
    SCPI_ResultUInt32(c, response);
    return SCPI_RES_OK;
}
scpi_result_t RP_DacSpiCountersQ(scpi_t* c) {
    uint32_t frames = 0, applies = 0;
    if (result(c, rp_DacSpiGetCounters(&frames, &applies), true) != SCPI_RES_OK) return SCPI_RES_ERR;
    SCPI_ResultUInt32(c, frames);
    SCPI_ResultUInt32(c, applies);
    return SCPI_RES_OK;
}
