/** @brief SCPI handlers for the LVDS CARRY4 TDC. */

#include "tdc.h"
#include "common.h"
#include "rp.h"
#include "scpi-parser-ext.h"

#include <inttypes.h>
#include <sstream>
#include <unistd.h>
#include <vector>

static const scpi_choice_def_t scpi_TdcMode[] = {
    {"SINGLE", RP_TDC_MODE_SINGLE},
    {"CONTINUOUS", RP_TDC_MODE_CONTINUOUS},
    {"CALIBRATION", RP_TDC_MODE_CALIBRATION},
    SCPI_CHOICE_LIST_END
};

static const scpi_choice_def_t scpi_TdcMmcmStep[] = {
    {"INCREASE", 1},
    {"DECREASE", 0},
    SCPI_CHOICE_LIST_END
};

static const scpi_choice_def_t scpi_TdcInput[] = {
    {"LVDS", RP_TDC_INPUT_LVDS},
    {"SINGLE", RP_TDC_INPUT_SINGLE},
    SCPI_CHOICE_LIST_END
};

static scpi_result_t tdc_error(scpi_t* context, int result, const char* message, bool query) {
    RP_LOG_CRIT("%s: %s", message, rp_GetError(result));
    if (query && getRetOnError())
        requestSendNewLine(context);
    return SCPI_RES_ERR;
}

static scpi_result_t tdc_u32(scpi_t* context, int result, uint32_t value, const char* message) {
    if (result != RP_OK)
        return tdc_error(context, result, message, true);
    SCPI_ResultUInt32Base(context, value, 10);
    return SCPI_RES_OK;
}

static scpi_result_t tdc_result(scpi_t* context, int result, const rp_tdc_result_t& value) {
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to read TDC result", true);
    std::ostringstream response;
    response << value.sequence_id << ',' << value.status << ','
             << value.coarse_cycles << ',' << value.fine_raw_index << ','
             << value.fine_time_ps << ',' << value.total_time_ps << ','
             << value.analogue_code;
    SCPI_ResultMnemonic(context, response.str().c_str());
    return SCPI_RES_OK;
}

static bool tdc_param_u32(scpi_t* context, uint32_t* value, const char* message) {
    if (!SCPI_ParamUInt32(context, value, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, message);
        return false;
    }
    return true;
}

scpi_result_t RP_TdcReset(scpi_t*) {
    int result = rp_TdcReset();
    return result == RP_OK ? SCPI_RES_OK : SCPI_RES_ERR;
}

scpi_result_t RP_TdcEnable(scpi_t* context) {
    scpi_bool_t enable = FALSE;
    if (!SCPI_ParamBool(context, &enable, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing TDC enable state.");
        return SCPI_RES_ERR;
    }
    int result = rp_TdcEnable(enable);
    return result == RP_OK ? SCPI_RES_OK : tdc_error(context, result, "Failed to set TDC enable", false);
}

scpi_result_t RP_TdcEnableQ(scpi_t* context) {
    bool enable = false;
    int result = rp_TdcGetEnable(&enable);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to get TDC enable", true);
    SCPI_ResultBool(context, enable);
    return SCPI_RES_OK;
}

scpi_result_t RP_TdcMode(scpi_t* context) {
    int32_t mode = 0;
    if (!SCPI_ParamChoice(context, scpi_TdcMode, &mode, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing TDC mode.");
        return SCPI_RES_ERR;
    }
    int result = rp_TdcSetMode((rp_tdc_mode_t)mode);
    return result == RP_OK ? SCPI_RES_OK : tdc_error(context, result, "Failed to set TDC mode", false);
}

scpi_result_t RP_TdcModeQ(scpi_t* context) {
    rp_tdc_mode_t mode = RP_TDC_MODE_SINGLE;
    int result = rp_TdcGetMode(&mode);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to get TDC mode", true);
    const char* name = nullptr;
    if (!SCPI_ChoiceToName(scpi_TdcMode, (int32_t)mode, &name))
        return SCPI_RES_ERR;
    SCPI_ResultMnemonic(context, name);
    return SCPI_RES_OK;
}

scpi_result_t RP_TdcInput(scpi_t* context) {
    int32_t input = 0;
    if (!SCPI_ParamChoice(context, scpi_TdcInput, &input, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_ILLEGAL_PARAMETER_VALUE, "Expected LVDS or SINGLE.");
        return SCPI_RES_ERR;
    }
    int result = rp_TdcSetInput((rp_tdc_input_t)input);
    return result == RP_OK ? SCPI_RES_OK :
           tdc_error(context, result, "Failed to select TDC input (requires v4+, disabled and idle)", false);
}

scpi_result_t RP_TdcInputQ(scpi_t* context) {
    rp_tdc_input_t input = RP_TDC_INPUT_LVDS;
    int result = rp_TdcGetInput(&input);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to get TDC input", true);
    const char* name = nullptr;
    if (!SCPI_ChoiceToName(scpi_TdcInput, (int32_t)input, &name))
        return SCPI_RES_ERR;
    SCPI_ResultMnemonic(context, name);
    return SCPI_RES_OK;
}

scpi_result_t RP_TdcTrigger(scpi_t* context) {
    int result = rp_TdcTrigger();
    return result == RP_OK ? SCPI_RES_OK : tdc_error(context, result, "Failed to trigger TDC", false);
}

scpi_result_t RP_TdcStatusQ(scpi_t* context) {
    uint32_t value = 0;
    int result = rp_TdcGetStatus(&value);
    return tdc_u32(context, result, value, "Failed to read TDC status");
}

scpi_result_t RP_TdcTapsQ(scpi_t* context) {
    uint32_t value = 0;
    int result = rp_TdcGetNumTaps(&value);
    return tdc_u32(context, result, value, "Failed to read TDC tap count");
}

scpi_result_t RP_TdcInternalTest(scpi_t* context) {
    scpi_bool_t enable = FALSE;
    if (!SCPI_ParamBool(context, &enable, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing internal TDC test state.");
        return SCPI_RES_ERR;
    }
    int result = rp_TdcSetInternalTest(enable);
    return result == RP_OK ? SCPI_RES_OK :
           tdc_error(context, result, "Failed to set internal TDC test", false);
}

scpi_result_t RP_TdcInternalTestQ(scpi_t* context) {
    bool enable = false;
    int result = rp_TdcGetInternalTest(&enable);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to get internal TDC test", true);
    SCPI_ResultBool(context, enable);
    return SCPI_RES_OK;
}

scpi_result_t RP_TdcLaunchPeriod(scpi_t* context) {
    uint32_t value = 0;
    if (!tdc_param_u32(context, &value, "Missing TDC launch period.")) return SCPI_RES_ERR;
    int result = rp_TdcSetLaunchPeriod(value);
    return result == RP_OK ? SCPI_RES_OK : tdc_error(context, result, "Failed to set TDC launch period", false);
}

scpi_result_t RP_TdcLaunchPeriodQ(scpi_t* context) {
    uint32_t value = 0;
    int result = rp_TdcGetLaunchPeriod(&value);
    return tdc_u32(context, result, value, "Failed to read TDC launch period");
}

scpi_result_t RP_TdcLaunchWidth(scpi_t* context) {
    uint32_t value = 0;
    if (!tdc_param_u32(context, &value, "Missing TDC launch width.")) return SCPI_RES_ERR;
    int result = rp_TdcSetLaunchWidth(value);
    return result == RP_OK ? SCPI_RES_OK : tdc_error(context, result, "Failed to set TDC launch width", false);
}

scpi_result_t RP_TdcLaunchWidthQ(scpi_t* context) {
    uint32_t value = 0;
    int result = rp_TdcGetLaunchWidth(&value);
    return tdc_u32(context, result, value, "Failed to read TDC launch width");
}

scpi_result_t RP_TdcTimeout(scpi_t* context) {
    uint32_t value = 0;
    if (!tdc_param_u32(context, &value, "Missing TDC timeout.")) return SCPI_RES_ERR;
    int result = rp_TdcSetTimeout(value);
    return result == RP_OK ? SCPI_RES_OK : tdc_error(context, result, "Failed to set TDC timeout", false);
}

scpi_result_t RP_TdcTimeoutQ(scpi_t* context) {
    uint32_t value = 0;
    int result = rp_TdcGetTimeout(&value);
    return tdc_u32(context, result, value, "Failed to read TDC timeout");
}

scpi_result_t RP_TdcFifoCountQ(scpi_t* context) {
    uint32_t value = 0;
    int result = rp_TdcGetFifoLevel(&value);
    return tdc_u32(context, result, value, "Failed to read TDC FIFO level");
}

scpi_result_t RP_TdcFifoDataQ(scpi_t* context) {
    rp_tdc_result_t result_value = {};
    return tdc_result(context, rp_TdcReadResult(&result_value), result_value);
}

scpi_result_t RP_TdcMeasureQ(scpi_t* context) {
    int result = rp_TdcTrigger();
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to trigger TDC measurement", true);

    uint32_t timeout_cycles = 0;
    result = rp_TdcGetTimeout(&timeout_cycles);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to read TDC timeout", true);

    uint64_t wait_us = ((uint64_t)timeout_cycles * 8u + 999u) / 1000u + 100000u;
    if (wait_us > 60000000u)
        wait_us = 60000000u;

    uint32_t level = 0;
    for (uint64_t elapsed = 0; elapsed <= wait_us; elapsed += 1000u) {
        result = rp_TdcGetFifoLevel(&level);
        if (result != RP_OK)
            return tdc_error(context, result, "Failed to read TDC FIFO level", true);
        if (level != 0)
            break;
        usleep(1000);
    }
    if (level == 0)
        return tdc_error(context, RP_EUF, "TDC measurement did not produce a FIFO result", true);

    rp_tdc_result_t value = {};
    return tdc_result(context, rp_TdcReadResult(&value), value);
}

scpi_result_t RP_TdcMeasureRawQ(scpi_t* context) {
    uint32_t taps = 0;
    int result = rp_TdcGetNumTaps(&taps);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to read TDC tap count", true);
    std::vector<uint32_t> words((taps + 31u) / 32u);
    result = rp_TdcGetRawCapture(0, words.data(), (uint32_t)words.size());
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to read TDC raw capture", true);
    std::ostringstream response;
    for (size_t i = 0; i < words.size(); ++i) {
        if (i) response << ',';
        response << words[i];
    }
    SCPI_ResultMnemonic(context, response.str().c_str());
    return SCPI_RES_OK;
}

scpi_result_t RP_TdcCalibrationClear(scpi_t* context) {
    int result = rp_TdcCalibrationClearHistogram();
    return result == RP_OK ? SCPI_RES_OK : tdc_error(context, result, "Failed to clear TDC histogram", false);
}

scpi_result_t RP_TdcCalibrationStart(scpi_t* context) {
    uint32_t events = 0;
    if (!tdc_param_u32(context, &events, "Missing TDC calibration event count.")) return SCPI_RES_ERR;
    int result = rp_TdcCalibrationStart(events);
    return result == RP_OK ? SCPI_RES_OK : tdc_error(context, result, "Failed to start TDC calibration", false);
}

scpi_result_t RP_TdcCalibrationStop(scpi_t* context) {
    int result = rp_TdcCalibrationStop();
    return result == RP_OK ? SCPI_RES_OK : tdc_error(context, result, "Failed to stop TDC calibration", false);
}

scpi_result_t RP_TdcCalibrationStatusQ(scpi_t* context) {
    uint32_t status = 0;
    uint32_t events = 0;
    int result = rp_TdcCalibrationGetStatus(&status, &events);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to read TDC calibration status", true);
    std::ostringstream response;
    response << status << ',' << events;
    SCPI_ResultMnemonic(context, response.str().c_str());
    return SCPI_RES_OK;
}

scpi_result_t RP_TdcCalibrationHistogramQ(scpi_t* context) {
    uint32_t taps = 0;
    int result = rp_TdcGetNumTaps(&taps);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to read TDC tap count", true);
    uint32_t start = 0;
    uint32_t count = taps;
    if (SCPI_ParamUInt32(context, &start, false)) {
        if (!SCPI_ParamUInt32(context, &count, true))
            return SCPI_RES_ERR;
    }
    if (start > taps || count > taps - start)
        return tdc_error(context, RP_EOOR, "TDC histogram range is invalid", true);
    std::vector<uint32_t> values(count);
    result = rp_TdcCalibrationReadHistogram(start, values.data(), count);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to read TDC histogram", true);
    std::ostringstream response;
    for (size_t i = 0; i < values.size(); ++i) {
        if (i) response << ',';
        response << values[i];
    }
    SCPI_ResultMnemonic(context, response.str().c_str());
    return SCPI_RES_OK;
}

scpi_result_t RP_TdcCalibrationLutWrite(scpi_t* context) {
    uint32_t start = 0;
    if (!tdc_param_u32(context, &start, "Missing TDC LUT start index.")) return SCPI_RES_ERR;
    std::vector<uint16_t> values;
    uint32_t value = 0;
    while (SCPI_ParamUInt32(context, &value, false)) {
        if (value > UINT16_MAX)
            return SCPI_RES_ERR;
        values.push_back((uint16_t)value);
    }
    if (values.empty())
        return SCPI_RES_ERR;
    int result = rp_TdcCalibrationWriteLut(start, values.data(), (uint32_t)values.size());
    return result == RP_OK ? SCPI_RES_OK : tdc_error(context, result, "Failed to write TDC LUT", false);
}

scpi_result_t RP_TdcCalibrationLutReadQ(scpi_t* context) {
    uint32_t start = 0;
    uint32_t count = 0;
    if (!tdc_param_u32(context, &start, "Missing TDC LUT start index.") ||
        !tdc_param_u32(context, &count, "Missing TDC LUT count.")) return SCPI_RES_ERR;
    uint32_t taps = 0;
    int result = rp_TdcGetNumTaps(&taps);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to read TDC tap count", true);
    if (start > taps || count > taps - start)
        return tdc_error(context, RP_EOOR, "TDC LUT range is invalid", true);
    std::vector<uint16_t> values(count);
    result = rp_TdcCalibrationReadLut(start, values.data(), count);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to read TDC LUT", true);
    std::ostringstream response;
    for (size_t i = 0; i < values.size(); ++i) {
        if (i) response << ',';
        response << values[i];
    }
    SCPI_ResultMnemonic(context, response.str().c_str());
    return SCPI_RES_OK;
}

scpi_result_t RP_TdcCalibrationLutActivate(scpi_t* context) {
    scpi_bool_t enable = FALSE;
    if (!SCPI_ParamBool(context, &enable, true))
        return SCPI_RES_ERR;
    int result = rp_TdcCalibrationActivate(enable);
    return result == RP_OK ? SCPI_RES_OK : tdc_error(context, result, "Failed to activate TDC LUT", false);
}

scpi_result_t RP_TdcCalibrationLutActivateQ(scpi_t* context) {
    bool enable = false;
    int result = rp_TdcCalibrationGetActive(&enable);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to read TDC LUT state", true);
    SCPI_ResultBool(context, enable);
    return SCPI_RES_OK;
}

scpi_result_t RP_TdcMmcmEnable(scpi_t* context) {
    scpi_bool_t enable = FALSE;
    if (!SCPI_ParamBool(context, &enable, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing MMCM sweep enable state.");
        return SCPI_RES_ERR;
    }
    int result = rp_TdcMmcmSetSweepEnable(enable);
    return result == RP_OK ? SCPI_RES_OK :
           tdc_error(context, result, "Failed to set MMCM sweep enable", false);
}

scpi_result_t RP_TdcMmcmEnableQ(scpi_t* context) {
    bool enable = false;
    int result = rp_TdcMmcmGetSweepEnable(&enable);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to get MMCM sweep enable", true);
    SCPI_ResultBool(context, enable);
    return SCPI_RES_OK;
}

scpi_result_t RP_TdcMmcmReset(scpi_t* context) {
    int result = rp_TdcMmcmReset();
    return result == RP_OK ? SCPI_RES_OK : tdc_error(context, result, "Failed to reset MMCM", false);
}

scpi_result_t RP_TdcMmcmStep(scpi_t* context) {
    int32_t increase = 0;
    if (!SCPI_ParamChoice(context, scpi_TdcMmcmStep, &increase, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing MMCM phase step direction.");
        return SCPI_RES_ERR;
    }
    int result = rp_TdcMmcmPhaseStep(increase != 0);
    return result == RP_OK ? SCPI_RES_OK :
           tdc_error(context, result, "Failed to request MMCM phase step", false);
}

scpi_result_t RP_TdcMmcmStatusQ(scpi_t* context) {
    uint32_t value = 0;
    int result = rp_TdcMmcmGetStatus(&value);
    return tdc_u32(context, result, value, "Failed to read MMCM status");
}

scpi_result_t RP_TdcMmcmTimeoutClear(scpi_t* context) {
    int result = rp_TdcMmcmClearTimeout();
    return result == RP_OK ? SCPI_RES_OK :
           tdc_error(context, result, "Failed to clear MMCM phase-step timeout", false);
}

scpi_result_t RP_TdcMmcmPhaseCountQ(scpi_t* context) {
    int32_t value = 0;
    int result = rp_TdcMmcmGetPhaseCount(&value);
    if (result != RP_OK)
        return tdc_error(context, result, "Failed to read MMCM phase count", true);
    SCPI_ResultInt32(context, value);
    return SCPI_RES_OK;
}

scpi_result_t RP_TdcMmcmPhaseClear(scpi_t* context) {
    int result = rp_TdcMmcmClearPhaseCount();
    return result == RP_OK ? SCPI_RES_OK :
           tdc_error(context, result, "Failed to clear MMCM phase count", false);
}

scpi_result_t RP_TdcMmcmCoarseDelay(scpi_t* context) {
    uint32_t value = 0;
    if (!tdc_param_u32(context, &value, "Missing MMCM coarse delay.")) return SCPI_RES_ERR;
    if (value > UINT16_MAX)
        return tdc_error(context, RP_EOOR, "MMCM coarse delay is out of range", false);
    int result = rp_TdcMmcmSetCoarseDelay((uint16_t)value);
    return result == RP_OK ? SCPI_RES_OK :
           tdc_error(context, result, "Failed to set MMCM coarse delay", false);
}

scpi_result_t RP_TdcMmcmCoarseDelayQ(scpi_t* context) {
    uint16_t value = 0;
    int result = rp_TdcMmcmGetCoarseDelay(&value);
    return tdc_u32(context, result, value, "Failed to read MMCM coarse delay");
}
