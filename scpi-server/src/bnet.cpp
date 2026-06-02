/**
 * @brief SCPI handlers for the custom BNET register block.
 */

#include "bnet.h"
#include "common.h"
#include "rp.h"

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

scpi_result_t RP_BNetReset(scpi_t* context) {
    int result = rp_BNetReset();
    if (result != RP_OK) {
        RP_LOG_CRIT("Failed to reset BNET: %s", rp_GetError(result));
        return SCPI_RES_ERR;
    }
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
