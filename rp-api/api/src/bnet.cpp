/**
 * @brief Custom butterfly-network register block implementation.
 */

#include "bnet.h"
#include "common.h"
#include "rp.h"

#include <stddef.h>

#define BNET_BASE_ADDR       0x00700000u
#define BNET_BASE_SIZE       0x00001000u

#define BNET_CONTROL_OFFSET  0x00u
#define BNET_STATUS_OFFSET   0x04u
#define BNET_CH_BASE_OFFSET  0x08u
#define BNET_OUT_BASE_OFFSET 0x28u
#define BNET_NUM_CH          8u
#define BNET_NUM_OUT         4u

#define BNET_CONTROL_START        0x1u
#define BNET_CONTROL_RESET        0x2u
#define BNET_CONTROL_LED_DEBUG    0x4u
#define BNET_CONTROL_LED6_HB_EN   0x8u

static volatile uint32_t* bnet_reg = NULL;

static inline void bnet_WriteReg(uint32_t offset, uint32_t value) {
    bnet_reg[offset / sizeof(uint32_t)] = value;
}

static inline uint32_t bnet_ReadReg(uint32_t offset) {
    return bnet_reg[offset / sizeof(uint32_t)];
}

static int bnet_CheckMap() {
    if (bnet_reg != NULL)
        return RP_OK;
    return bnet_Init();
}

int bnet_Init() {
    if (bnet_reg != NULL)
        return RP_OK;
    return cmn_Map(BNET_BASE_SIZE, BNET_BASE_ADDR, (void**)&bnet_reg);
}

int bnet_Release() {
    if (bnet_reg == NULL)
        return RP_OK;
    return cmn_Unmap(BNET_BASE_SIZE, (void**)&bnet_reg);
}

int rp_BNetSetChannelData(uint32_t channel, int32_t value) {
    if (channel >= BNET_NUM_CH)
        return RP_EOOR;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    bnet_WriteReg(BNET_CH_BASE_OFFSET + sizeof(uint32_t) * channel, (uint32_t)value);
    return RP_OK;
}

int rp_BNetGetChannelData(uint32_t channel, int32_t* value) {
    if (value == NULL)
        return RP_UIA;
    if (channel >= BNET_NUM_CH)
        return RP_EOOR;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *value = (int32_t)bnet_ReadReg(BNET_CH_BASE_OFFSET + sizeof(uint32_t) * channel);
    return RP_OK;
}

int rp_BNetStart() {
    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    uint32_t control = bnet_ReadReg(BNET_CONTROL_OFFSET);
    bnet_WriteReg(BNET_CONTROL_OFFSET, control | BNET_CONTROL_START);
    return RP_OK;
}

int rp_BNetReset() {
    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    bnet_WriteReg(BNET_CONTROL_OFFSET, BNET_CONTROL_RESET);
    bnet_WriteReg(BNET_CONTROL_OFFSET, 0u);
    return RP_OK;
}

int rp_BNetGetStatus(uint32_t* status) {
    if (status == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *status = bnet_ReadReg(BNET_STATUS_OFFSET);
    return RP_OK;
}

int rp_BNetGetOutputData(uint32_t index, int32_t* value) {
    if (value == NULL)
        return RP_UIA;
    if (index >= BNET_NUM_OUT)
        return RP_EOOR;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *value = (int32_t)bnet_ReadReg(BNET_OUT_BASE_OFFSET + sizeof(uint32_t) * index);
    return RP_OK;
}

int rp_BNetSetLed6Heartbeat(bool enable) {
    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    uint32_t control = bnet_ReadReg(BNET_CONTROL_OFFSET);
    control &= ~BNET_CONTROL_LED_DEBUG;
    if (enable)
        control |= BNET_CONTROL_LED6_HB_EN;
    else
        control &= ~BNET_CONTROL_LED6_HB_EN;

    bnet_WriteReg(BNET_CONTROL_OFFSET, control);
    return RP_OK;
}

int rp_BNetGetLed6Heartbeat(bool* enable) {
    if (enable == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *enable = (bnet_ReadReg(BNET_CONTROL_OFFSET) & BNET_CONTROL_LED6_HB_EN) != 0;
    return RP_OK;
}
