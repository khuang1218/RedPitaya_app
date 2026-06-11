/**
 * @brief SCPI handlers for the custom BNET register block.
 */

#include "bnet.h"
#include "common.h"
#include "rp.h"
#include "scpi-parser-ext.h"

#include <stdlib.h>

static const scpi_choice_def_t scpi_BNetMode[] = {{"ASG", 0}, {"ADC", 1}, {"DDR", 2}, SCPI_CHOICE_LIST_END};

static int parse_bnet_index(scpi_t* context, int32_t min_index, int32_t max_index, uint32_t* index) {
    int32_t cmd[1];

    if (!SCPI_CommandNumbers(context, cmd, 1, min_index)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing command index.");
        return RP_UIA;
    }

    if ((cmd[0] < min_index) || (cmd[0] > max_index)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "BNET index out of range.");
        return RP_EOOR;
    }

    *index = (uint32_t)cmd[0];
    return RP_OK;
}

static int parse_bnet_indices(scpi_t* context, int32_t min_first, int32_t max_first, uint32_t* first, int32_t min_second, int32_t max_second, uint32_t* second) {
    int32_t cmd[2] = {-1, -1};

    if (!SCPI_CommandNumbers(context, cmd, 2, -1)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing command index.");
        return RP_UIA;
    }

    if ((cmd[0] < min_first) || (cmd[0] > max_first) || (cmd[1] < min_second) || (cmd[1] > max_second)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "BNET index out of range.");
        return RP_EOOR;
    }

    *first = (uint32_t)cmd[0];
    *second = (uint32_t)cmd[1];
    return RP_OK;
}

static int parse_bnet_three_indices(scpi_t* context,
                                    int32_t min_first, int32_t max_first, uint32_t* first,
                                    int32_t min_second, int32_t max_second, uint32_t* second,
                                    int32_t min_third, int32_t max_third, uint32_t* third) {
    int32_t cmd[3] = {-1, -1, -1};

    if (!SCPI_CommandNumbers(context, cmd, 3, -1)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing command index.");
        return RP_UIA;
    }

    if ((cmd[0] < min_first) || (cmd[0] > max_first) ||
        (cmd[1] < min_second) || (cmd[1] > max_second) ||
        (cmd[2] < min_third) || (cmd[2] > max_third)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "BNET index out of range.");
        return RP_EOOR;
    }

    *first = (uint32_t)cmd[0];
    *second = (uint32_t)cmd[1];
    *third = (uint32_t)cmd[2];
    return RP_OK;
}

static scpi_result_t bnet_return_error(scpi_t* context, int result, const char* message, bool query) {
    RP_LOG_CRIT("%s: %s", message, rp_GetError(result));
    if (query && getRetOnError())
        requestSendNewLine(context);
    return SCPI_RES_ERR;
}

static scpi_result_t bnet_result_uint32(scpi_t* context, int result, uint32_t value, const char* message) {
    if (result != RP_OK)
        return bnet_return_error(context, result, message, true);

    SCPI_ResultUInt32Base(context, value, 10);
    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetReset(scpi_t* context) {
    int result = rp_BNetReset();
    if (result != RP_OK) {
        RP_LOG_CRIT("Failed to reset BNET: %s", rp_GetError(result));
        return SCPI_RES_ERR;
    }
    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetCommitAll(scpi_t* context) {
    int result = rp_BNetCommitAllEnabledStreams();
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to commit all enabled BNET streams", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetMode(scpi_t* context) {
    int32_t mode = 0;
    if (!SCPI_ParamChoice(context, scpi_BNetMode, &mode, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET input mode.");
        return SCPI_RES_ERR;
    }

    int result = rp_BNetSetInputMode((uint32_t)mode);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to set BNET input mode", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetModeQ(scpi_t* context) {
    uint32_t mode = 0;
    int result = rp_BNetGetInputMode(&mode);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to get BNET input mode", true);

    const char* name = nullptr;
    if (!SCPI_ChoiceToName(scpi_BNetMode, (int32_t)mode, &name)) {
        SCPI_LOG_ERR(SCPI_ERROR_EXECUTION_ERROR, "Failed to parse BNET input mode.")
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    SCPI_ResultMnemonic(context, name);
    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetConfig(scpi_t* context) {
    uint32_t config = 0;
    if (!SCPI_ParamUInt32(context, &config, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET configuration value.");
        return SCPI_RES_ERR;
    }

    int result = rp_BNetSetConfig(config);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to set BNET configuration", false);

    return SCPI_RES_OK;
}

scpi_result_t RP_BNetConfigQ(scpi_t* context) {
    uint32_t config = 0;
    int result = rp_BNetGetConfig(&config);
    return bnet_result_uint32(context, result, config, "Failed to get BNET configuration");
}

scpi_result_t RP_BNetStaticWeightReuse(scpi_t* context) {
    scpi_bool_t enable = FALSE;
    if (!SCPI_ParamBool(context, &enable, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET static weight reuse state.");
        return SCPI_RES_ERR;
    }

    int result = rp_BNetSetStaticWeightReuse(enable);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to set BNET static weight reuse state", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetStaticWeightReuseQ(scpi_t* context) {
    bool enable = false;
    int result = rp_BNetGetStaticWeightReuse(&enable);
    return bnet_result_uint32(context, result, enable ? 1u : 0u,
                              "Failed to get BNET static weight reuse state");
}

scpi_result_t RP_BNetStaticPipeline(scpi_t* context) {
    scpi_bool_t enable = FALSE;
    if (!SCPI_ParamBool(context, &enable, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET static pipeline state.");
        return SCPI_RES_ERR;
    }

    int result = rp_BNetSetStaticPipeline(enable);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to set BNET static pipeline state", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetStaticPipelineQ(scpi_t* context) {
    bool enable = false;
    int result = rp_BNetGetStaticPipeline(&enable);
    return bnet_result_uint32(context, result, enable ? 1u : 0u,
                              "Failed to get BNET static pipeline state");
}

scpi_result_t RP_BNetVectorLength(scpi_t* context) {
    uint32_t samples = 0;
    if (!SCPI_ParamUInt32(context, &samples, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET vector length.");
        return SCPI_RES_ERR;
    }

    int result = rp_BNetSetVectorLength(samples);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to set BNET vector length", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetVectorLengthQ(scpi_t* context) {
    uint32_t samples = 0;
    int result = rp_BNetGetVectorLength(&samples);
    return bnet_result_uint32(context, result, samples, "Failed to get BNET vector length");
}

scpi_result_t RP_BNetStreamCountQ(scpi_t* context) {
    uint32_t count = 0;
    int result = rp_BNetGetStreamCount(&count);
    return bnet_result_uint32(context, result, count, "Failed to get BNET stream count");
}

scpi_result_t RP_BNetActiveMaskQ(scpi_t* context) {
    uint32_t mask = 0;
    int result = rp_BNetGetActiveMask(&mask);
    return bnet_result_uint32(context, result, mask, "Failed to get BNET active stream mask");
}

scpi_result_t RP_BNetPendingMaskQ(scpi_t* context) {
    uint32_t mask = 0;
    int result = rp_BNetGetPendingMask(&mask);
    return bnet_result_uint32(context, result, mask, "Failed to get BNET pending stream mask");
}

scpi_result_t RP_BNetErrorMaskQ(scpi_t* context) {
    uint32_t mask = 0;
    int result = rp_BNetGetErrorMask(&mask);
    return bnet_result_uint32(context, result, mask, "Failed to get BNET error stream mask");
}

scpi_result_t RP_BNetTimingQ(scpi_t* context) {
    uint32_t index = 0;
    uint32_t cycles = 0;
    int result = parse_bnet_index(context, 0, 3, &index);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    result = rp_BNetGetTiming(index, &cycles);
    return bnet_result_uint32(context, result, cycles, "Failed to get BNET timing counter");
}

scpi_result_t RP_BNetStreamBase(scpi_t* context) {
    uint32_t stream = 0;
    uint32_t buffer = 0;
    uint32_t address = 0;
    int result = parse_bnet_indices(context, 0, 7, &stream, 0, 1, &buffer);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    if (!SCPI_ParamUInt32(context, &address, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET stream base address.");
        return SCPI_RES_ERR;
    }

    result = rp_BNetSetStreamBase(stream, buffer, address);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to set BNET stream base address", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetStreamBaseQ(scpi_t* context) {
    uint32_t stream = 0;
    uint32_t buffer = 0;
    uint32_t address = 0;
    int result = parse_bnet_indices(context, 0, 7, &stream, 0, 1, &buffer);
    if (result != RP_OK) {
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    result = rp_BNetGetStreamBase(stream, buffer, &address);
    return bnet_result_uint32(context, result, address, "Failed to get BNET stream base address");
}

scpi_result_t RP_BNetStreamLength(scpi_t* context) {
    uint32_t stream = 0;
    uint32_t length = 0;
    int result = parse_bnet_index(context, 0, 7, &stream);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    if (!SCPI_ParamUInt32(context, &length, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET stream length.");
        return SCPI_RES_ERR;
    }

    result = rp_BNetSetStreamLength(stream, length);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to set BNET stream length", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetStreamLengthQ(scpi_t* context) {
    uint32_t stream = 0;
    uint32_t length = 0;
    int result = parse_bnet_index(context, 0, 7, &stream);
    if (result != RP_OK) {
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    result = rp_BNetGetStreamLength(stream, &length);
    return bnet_result_uint32(context, result, length, "Failed to get BNET stream length");
}

scpi_result_t RP_BNetStreamStride(scpi_t* context) {
    uint32_t stream = 0;
    uint32_t stride = 0;
    int result = parse_bnet_index(context, 0, 7, &stream);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    if (!SCPI_ParamUInt32(context, &stride, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET stream stride.");
        return SCPI_RES_ERR;
    }

    result = rp_BNetSetStreamStride(stream, stride);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to set BNET stream stride", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetStreamStrideQ(scpi_t* context) {
    uint32_t stream = 0;
    uint32_t stride = 0;
    int result = parse_bnet_index(context, 0, 7, &stream);
    if (result != RP_OK) {
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    result = rp_BNetGetStreamStride(stream, &stride);
    return bnet_result_uint32(context, result, stride, "Failed to get BNET stream stride");
}

scpi_result_t RP_BNetStreamFormat(scpi_t* context) {
    uint32_t stream = 0;
    uint32_t format = 0;
    int result = parse_bnet_index(context, 0, 7, &stream);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    if (!SCPI_ParamUInt32(context, &format, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET stream format.");
        return SCPI_RES_ERR;
    }

    result = rp_BNetSetStreamFormat(stream, format);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to set BNET stream format", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetStreamFormatQ(scpi_t* context) {
    uint32_t stream = 0;
    uint32_t format = 0;
    int result = parse_bnet_index(context, 0, 7, &stream);
    if (result != RP_OK) {
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    result = rp_BNetGetStreamFormat(stream, &format);
    return bnet_result_uint32(context, result, format, "Failed to get BNET stream format");
}

scpi_result_t RP_BNetStreamEnable(scpi_t* context) {
    uint32_t stream = 0;
    scpi_bool_t enable = FALSE;
    int result = parse_bnet_index(context, 0, 7, &stream);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    if (!SCPI_ParamBool(context, &enable, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET stream enable state.");
        return SCPI_RES_ERR;
    }

    result = rp_BNetEnableStream(stream, enable);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to set BNET stream enable state", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetStreamEnableQ(scpi_t* context) {
    uint32_t stream = 0;
    bool enable = false;
    int result = parse_bnet_index(context, 0, 7, &stream);
    if (result != RP_OK) {
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    result = rp_BNetGetStreamEnable(stream, &enable);
    return bnet_result_uint32(context, result, enable ? 1u : 0u, "Failed to get BNET stream enable state");
}

scpi_result_t RP_BNetStreamCommit(scpi_t* context) {
    uint32_t stream = 0;
    uint32_t buffer = 0;
    int result = parse_bnet_indices(context, 0, 7, &stream, 0, 1, &buffer);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    result = rp_BNetCommitStreamBuffer(stream, buffer);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to commit BNET stream buffer", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetStreamSwap(scpi_t* context) {
    uint32_t stream = 0;
    int result = parse_bnet_index(context, 0, 7, &stream);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    result = rp_BNetForceStreamSwap(stream);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to force BNET stream swap", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetStreamClear(scpi_t* context) {
    uint32_t stream = 0;
    int result = parse_bnet_index(context, 0, 7, &stream);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    result = rp_BNetClearStreamError(stream);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to clear BNET stream error", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetStreamStatusQ(scpi_t* context) {
    uint32_t stream = 0;
    uint32_t status = 0;
    int result = parse_bnet_index(context, 0, 7, &stream);
    if (result != RP_OK) {
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    result = rp_BNetGetStreamStatus(stream, &status);
    return bnet_result_uint32(context, result, status, "Failed to get BNET stream status");
}

scpi_result_t RP_BNetStreamReadPtrQ(scpi_t* context) {
    uint32_t stream = 0;
    uint32_t read_ptr = 0;
    int result = parse_bnet_index(context, 0, 7, &stream);
    if (result != RP_OK) {
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    result = rp_BNetGetStreamReadPtr(stream, &read_ptr);
    return bnet_result_uint32(context, result, read_ptr, "Failed to get BNET stream read pointer");
}

scpi_result_t RP_BNetStreamDebugQ(scpi_t* context) {
    uint32_t stream = 0;
    uint32_t debug_index = 0;
    uint32_t value = 0;
    int result = parse_bnet_indices(context, 0, 7, &stream, 0, 1, &debug_index);
    if (result != RP_OK) {
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    result = rp_BNetGetStreamDebug(stream, debug_index, &value);
    return bnet_result_uint32(context, result, value, "Failed to get BNET stream debug register");
}

scpi_result_t RP_BNetDdrStartQ(scpi_t* context) {
    uint32_t start = 0;
    uint32_t size = 0;
    int result = rp_BNetDdrGetMemoryRegion(&start, &size);
    return bnet_result_uint32(context, result, start, "Failed to get BNET DDR memory start");
}

scpi_result_t RP_BNetDdrSizeQ(scpi_t* context) {
    uint32_t start = 0;
    uint32_t size = 0;
    int result = rp_BNetDdrGetMemoryRegion(&start, &size);
    return bnet_result_uint32(context, result, size, "Failed to get BNET DDR memory size");
}

scpi_result_t RP_BNetDdrSlotReserve(scpi_t* context) {
    uint32_t slot = 0;
    uint32_t address = 0;
    uint32_t size = 0;
    int result = parse_bnet_index(context, 0, 7, &slot);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    if (!SCPI_ParamUInt32(context, &address, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET DDR slot address.");
        return SCPI_RES_ERR;
    }

    if (!SCPI_ParamUInt32(context, &size, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET DDR slot size.");
        return SCPI_RES_ERR;
    }

    result = rp_BNetDdrReserve(slot, address, size);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to reserve BNET DDR slot", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetDdrSlotRelease(scpi_t* context) {
    uint32_t slot = 0;
    int result = parse_bnet_index(context, 0, 7, &slot);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    result = rp_BNetDdrRelease(slot);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to release BNET DDR slot", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetDdrSlotBaseQ(scpi_t* context) {
    uint32_t slot = 0;
    uint32_t address = 0;
    int result = parse_bnet_index(context, 0, 7, &slot);
    if (result != RP_OK) {
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    result = rp_BNetDdrGetSlotBase(slot, &address);
    return bnet_result_uint32(context, result, address, "Failed to get BNET DDR slot base address");
}

scpi_result_t RP_BNetDdrSlotSizeQ(scpi_t* context) {
    uint32_t slot = 0;
    uint32_t size = 0;
    int result = parse_bnet_index(context, 0, 7, &slot);
    if (result != RP_OK) {
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    result = rp_BNetDdrGetSlotSize(slot, &size);
    return bnet_result_uint32(context, result, size, "Failed to get BNET DDR slot size");
}

scpi_result_t RP_BNetDdrSlotAttach(scpi_t* context) {
    uint32_t slot = 0;
    uint32_t stream = 0;
    uint32_t buffer = 0;
    int result = parse_bnet_three_indices(context, 0, 7, &slot, 0, 7, &stream, 0, 1, &buffer);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    result = rp_BNetDdrAttachStreamBuffer(slot, stream, buffer);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to attach BNET DDR slot to stream buffer", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetDdrSlotData(scpi_t* context) {
    uint32_t slot = 0;
    uint32_t offset_bytes = 0;
    uint32_t bytes = 0;
    int result = parse_bnet_three_indices(context, 0, 7, &slot, 0, 0x7fffffff, &offset_bytes, 0, 0x7fffffff, &bytes);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    uint8_t* buffer = (uint8_t*)malloc(bytes);
    if (!buffer) {
        SCPI_LOG_ERR(SCPI_ERROR_EXECUTION_ERROR, "Failed allocate BNET DDR upload buffer.");
        return SCPI_RES_ERR;
    }

    uint32_t buf_size = bytes;
    if (!SCPI_ParamBufferUInt8(context, buffer, &buf_size, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_EXECUTION_ERROR, "Failed get BNET DDR upload data.");
        free(buffer);
        return SCPI_RES_ERR;
    }

    if (buf_size != bytes) {
        SCPI_LOG_ERR(SCPI_ERROR_EXECUTION_ERROR, "Wrong BNET DDR upload data length.");
        free(buffer);
        return SCPI_RES_ERR;
    }

    result = rp_BNetDdrWriteRaw(slot, offset_bytes, buffer, bytes);
    free(buffer);
    if (result != RP_OK)
        return bnet_return_error(context, result, "Failed to write BNET DDR upload data", false);

    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetStart(scpi_t* context) {
    int result = rp_BNetStart();
    if (result != RP_OK) {
        RP_LOG_CRIT("Failed to start BNET: %s", rp_GetError(result));
        return SCPI_RES_ERR;
    }
    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetStatusQ(scpi_t* context) {
    uint32_t status = 0;
    int result = rp_BNetGetStatus(&status);
    if (result != RP_OK) {
        RP_LOG_CRIT("Failed to get BNET status: %s", rp_GetError(result));
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }
    SCPI_ResultUInt32Base(context, status, 10);
    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetChannelData(scpi_t* context) {
    uint32_t channel = 0;
    int32_t value = 0;
    int result = parse_bnet_index(context, 0, 7, &channel);
    if (result != RP_OK)
        return SCPI_RES_ERR;

    if (!SCPI_ParamInt32(context, &value, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing BNET channel value.");
        return SCPI_RES_ERR;
    }

    result = rp_BNetSetChannelData(channel, value);
    if (result != RP_OK) {
        RP_LOG_CRIT("Failed to set BNET channel data: %s", rp_GetError(result));
        return SCPI_RES_ERR;
    }
    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetChannelDataQ(scpi_t* context) {
    uint32_t channel = 0;
    int32_t value = 0;
    int result = parse_bnet_index(context, 0, 7, &channel);
    if (result != RP_OK) {
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    result = rp_BNetGetChannelData(channel, &value);
    if (result != RP_OK) {
        RP_LOG_CRIT("Failed to get BNET channel data: %s", rp_GetError(result));
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }
    SCPI_ResultInt32(context, value);
    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetOutputDataQ(scpi_t* context) {
    uint32_t index = 0;
    int32_t value = 0;
    int result = parse_bnet_index(context, 0, 3, &index);
    if (result != RP_OK) {
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }

    result = rp_BNetGetOutputData(index, &value);
    if (result != RP_OK) {
        RP_LOG_CRIT("Failed to get BNET output data: %s", rp_GetError(result));
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }
    SCPI_ResultInt32(context, value);
    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetLed6Heartbeat(scpi_t* context) {
    scpi_bool_t enable = FALSE;
    if (!SCPI_ParamBool(context, &enable, true)) {
        SCPI_LOG_ERR(SCPI_ERROR_MISSING_PARAMETER, "Missing LED6 heartbeat state.");
        return SCPI_RES_ERR;
    }

    int result = rp_BNetSetLed6Heartbeat(enable);
    if (result != RP_OK) {
        RP_LOG_CRIT("Failed to set BNET LED6 heartbeat: %s", rp_GetError(result));
        return SCPI_RES_ERR;
    }
    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}

scpi_result_t RP_BNetLed6HeartbeatQ(scpi_t* context) {
    bool enable = false;
    int result = rp_BNetGetLed6Heartbeat(&enable);
    if (result != RP_OK) {
        RP_LOG_CRIT("Failed to get BNET LED6 heartbeat: %s", rp_GetError(result));
        if (getRetOnError())
            requestSendNewLine(context);
        return SCPI_RES_ERR;
    }
    SCPI_ResultUInt32Base(context, enable ? 1u : 0u, 10);
    RP_LOG_INFO("%s", rp_GetError(result))
    return SCPI_RES_OK;
}
