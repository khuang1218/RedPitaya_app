/**
 * @brief Custom butterfly-network register block implementation.
 */

#include "bnet.h"
#include "axi_manager.h"
#include "common.h"
#include "rp.h"

#include <stddef.h>
#include <string.h>

#define BNET_BASE_ADDR       0x00700000u
#define BNET_BASE_SIZE       0x00001000u

#define BNET_CONTROL_OFFSET  0x00u
#define BNET_STATUS_OFFSET   0x04u
#define BNET_CH_BASE_OFFSET  0x08u
#define BNET_OUT_BASE_OFFSET 0x28u
#define BNET_VECTOR_LEN_OFFSET    0x38u
#define BNET_STREAM_COUNT_OFFSET  0x3Cu
#define BNET_ACTIVE_MASK_OFFSET   0x40u
#define BNET_PENDING_MASK_OFFSET  0x44u
#define BNET_ERROR_MASK_OFFSET    0x48u
#define BNET_CONFIG_OFFSET        0x4Cu
#define BNET_TIME_TOTAL_OFFSET    0x50u
#define BNET_TIME_LOAD_OFFSET     0x54u
#define BNET_TIME_COMPUTE_OFFSET  0x58u
#define BNET_TIME_PLAYBACK_OFFSET 0x5Cu
#define BNET_TIME_INPUT_LOAD_OFFSET 0x60u
#define BNET_TIME_LATENCY_OFFSET    0x64u
#define BNET_CAPTURE_COUNT_OFFSET   0x68u
#define BNET_CAPTURE_ADDR_OFFSET    0x6Cu
#define BNET_CAPTURE_DATA_OFFSET    0x70u
#define BNET_CAPTURE_STATUS_OFFSET  0x74u
#define BNET_WEIGHT_BANK_OFFSET     0x78u
#define BNET_REGISTER_SETTLE_READS  16u
#define BNET_CAPTURE_READ_SETTLE_READS 16u
#define BNET_STREAM_BASE_OFFSET   0x100u
#define BNET_STREAM_STRIDE        0x40u
#define BNET_NUM_CH          8u
#define BNET_NUM_OUT         4u
#define BNET_MAX_STREAMS     8u
#define BNET_MAX_DDR_SLOTS   8u

#define BNET_CONTROL_START        0x1u
#define BNET_CONTROL_RESET        0x2u
#define BNET_CONTROL_LED_DEBUG    0x4u
#define BNET_CONTROL_LED6_HB_EN   0x8u
#define BNET_CONTROL_COMMIT_ALL   0x20u

#define BNET_STREAM_BASE0_OFFSET   0x00u
#define BNET_STREAM_BASE1_OFFSET   0x04u
#define BNET_STREAM_LENGTH_OFFSET  0x08u
#define BNET_STREAM_STRIDE_OFFSET  0x0Cu
#define BNET_STREAM_FORMAT_OFFSET  0x10u
#define BNET_STREAM_CONTROL_OFFSET 0x14u
#define BNET_STREAM_STATUS_OFFSET  0x18u
#define BNET_STREAM_RPTR_OFFSET    0x1Cu
#define BNET_STREAM_DBG0_OFFSET    0x20u
#define BNET_STREAM_DBG1_OFFSET    0x24u

#define BNET_STREAM_CONTROL_ENABLE      0x01u
#define BNET_STREAM_CONTROL_COMMIT_BUF0 0x02u
#define BNET_STREAM_CONTROL_COMMIT_BUF1 0x04u
#define BNET_STREAM_CONTROL_FORCE_SWAP  0x08u
#define BNET_STREAM_CONTROL_CLEAR_ERROR 0x10u

#define BNET_CONFIG_INPUT_MODE_MASK     0x03u
#define BNET_CONFIG_STATIC_WEIGHT_REUSE 0x10u
#define BNET_CONFIG_STATIC_PIPELINE     0x20u
#define BNET_CONFIG_SINGLE_DAC_OUTPUT   0x40u
#define BNET_CONFIG_SPLIT_DAC_OUTPUT    0x80u
#define BNET_CONFIG_COMBINE_ADC_INPUT   0x100u
#define BNET_CONFIG_COMBINE_ADC_PHASE   0x200u
#define BNET_WEIGHT_BANK_SELECTED       0x80000000u

static volatile uint32_t* bnet_reg = NULL;

typedef struct {
    uint64_t index;
    uint32_t address;
    uint32_t size;
} bnet_ddr_slot_t;

static bnet_ddr_slot_t bnet_ddr_slots[BNET_MAX_DDR_SLOTS];

static inline void bnet_WriteReg(uint32_t offset, uint32_t value) {
    bnet_reg[offset / sizeof(uint32_t)] = value;
}

static inline uint32_t bnet_ReadReg(uint32_t offset) {
    return bnet_reg[offset / sizeof(uint32_t)];
}

static uint32_t bnet_ReadRegSettled(uint32_t offset) {
    uint32_t value = 0;
    for (uint32_t i = 0; i < BNET_REGISTER_SETTLE_READS; ++i)
        value = bnet_ReadReg(offset);
    return value;
}

static int16_t bnet_ReadCaptureSample(uint32_t index) {
    bnet_WriteReg(BNET_CAPTURE_ADDR_OFFSET, index);

    // CAPTURE_ADDR crosses the system-bus bridge before addressing a
    // synchronous block RAM in the adc_clk domain. Keep the requested address
    // stable while the read pipeline settles; otherwise sequential block reads
    // can return samples from several addresses earlier.
    (void)bnet_ReadReg(BNET_CAPTURE_ADDR_OFFSET);
    uint32_t value = 0;
    for (uint32_t i = 0; i < BNET_CAPTURE_READ_SETTLE_READS; ++i)
        value = bnet_ReadReg(BNET_CAPTURE_DATA_OFFSET);
    return (int16_t)value;
}

static int bnet_CheckMap() {
    if (bnet_reg != NULL)
        return RP_OK;
    return bnet_Init();
}

static int bnet_SetConfigBit(uint32_t mask, bool enable) {
    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    uint32_t config = bnet_ReadRegSettled(BNET_CONFIG_OFFSET);
    if (enable)
        config |= mask;
    else
        config &= ~mask;
    bnet_WriteReg(BNET_CONFIG_OFFSET, config);
    return (bnet_ReadRegSettled(BNET_CONFIG_OFFSET) & mask) ==
                   (enable ? mask : 0u) ? RP_OK : RP_EOP;
}

static int bnet_GetConfigBit(uint32_t mask, bool* enable) {
    if (enable == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *enable = (bnet_ReadRegSettled(BNET_CONFIG_OFFSET) & mask) != 0;
    return RP_OK;
}

static int bnet_CheckStream(uint32_t stream) {
    if (stream >= BNET_MAX_STREAMS)
        return RP_EOOR;
    return RP_OK;
}

static int bnet_CheckDdrSlot(uint32_t slot) {
    if (slot >= BNET_MAX_DDR_SLOTS)
        return RP_EOOR;
    return RP_OK;
}

static int bnet_CheckDdrSlotReserved(uint32_t slot) {
    int ret = bnet_CheckDdrSlot(slot);
    if (ret != RP_OK)
        return ret;
    return bnet_ddr_slots[slot].index == 0 ? RP_EOOR : RP_OK;
}

static inline uint32_t bnet_StreamRegOffset(uint32_t stream, uint32_t reg_offset) {
    return BNET_STREAM_BASE_OFFSET + BNET_STREAM_STRIDE * stream + reg_offset;
}

static uint32_t bnet_GetStreamEnableBit(uint32_t stream) {
    return bnet_ReadReg(bnet_StreamRegOffset(stream, BNET_STREAM_CONTROL_OFFSET)) &
           BNET_STREAM_CONTROL_ENABLE;
}

int bnet_Init() {
    if (bnet_reg != NULL)
        return RP_OK;
    return cmn_Map(BNET_BASE_SIZE, BNET_BASE_ADDR, (void**)&bnet_reg);
}

int bnet_Release() {
    for (uint32_t slot = 0; slot < BNET_MAX_DDR_SLOTS; ++slot) {
        if (bnet_ddr_slots[slot].index != 0) {
            axi_releaseMemory(bnet_ddr_slots[slot].index);
            bnet_ddr_slots[slot].index = 0;
            bnet_ddr_slots[slot].address = 0;
            bnet_ddr_slots[slot].size = 0;
        }
    }

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

    uint32_t vector_len = bnet_ReadRegSettled(BNET_VECTOR_LEN_OFFSET);
    uint32_t bank_status = bnet_ReadRegSettled(BNET_WEIGHT_BANK_OFFSET);
    if (vector_len != 4096u && (bank_status & BNET_WEIGHT_BANK_SELECTED) == 0)
        return RP_EIPV;

    uint32_t control = bnet_ReadReg(BNET_CONTROL_OFFSET);
    bnet_WriteReg(BNET_CONTROL_OFFSET, control | BNET_CONTROL_START);
    return RP_OK;
}

int rp_BNetCommitAllEnabledStreams() {
    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    uint32_t control = bnet_ReadReg(BNET_CONTROL_OFFSET);
    bnet_WriteReg(BNET_CONTROL_OFFSET, control | BNET_CONTROL_COMMIT_ALL);
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

int rp_BNetSetInputMode(uint32_t mode) {
    if ((mode & ~BNET_CONFIG_INPUT_MODE_MASK) != 0)
        return RP_EOOR;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    uint32_t config = bnet_ReadReg(BNET_CONFIG_OFFSET);
    config &= ~BNET_CONFIG_INPUT_MODE_MASK;
    config |= mode & BNET_CONFIG_INPUT_MODE_MASK;
    bnet_WriteReg(BNET_CONFIG_OFFSET, config);
    return RP_OK;
}

int rp_BNetGetInputMode(uint32_t* mode) {
    if (mode == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *mode = bnet_ReadReg(BNET_CONFIG_OFFSET) & BNET_CONFIG_INPUT_MODE_MASK;
    return RP_OK;
}

int rp_BNetSetConfig(uint32_t config) {
    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    bnet_WriteReg(BNET_CONFIG_OFFSET, config);
    return RP_OK;
}

int rp_BNetGetConfig(uint32_t* config) {
    if (config == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *config = bnet_ReadReg(BNET_CONFIG_OFFSET);
    return RP_OK;
}

int rp_BNetSetStaticWeightReuse(bool enable) {
    return bnet_SetConfigBit(BNET_CONFIG_STATIC_WEIGHT_REUSE, enable);
}

int rp_BNetGetStaticWeightReuse(bool* enable) {
    return bnet_GetConfigBit(BNET_CONFIG_STATIC_WEIGHT_REUSE, enable);
}

int rp_BNetSetStaticPipeline(bool enable) {
    return bnet_SetConfigBit(BNET_CONFIG_STATIC_PIPELINE, enable);
}

int rp_BNetGetStaticPipeline(bool* enable) {
    return bnet_GetConfigBit(BNET_CONFIG_STATIC_PIPELINE, enable);
}

int rp_BNetSetSingleDacOutput(bool enable) {
    return bnet_SetConfigBit(BNET_CONFIG_SINGLE_DAC_OUTPUT, enable);
}

int rp_BNetGetSingleDacOutput(bool* enable) {
    return bnet_GetConfigBit(BNET_CONFIG_SINGLE_DAC_OUTPUT, enable);
}

int rp_BNetSetSplitDacOutput(bool enable) {
    return bnet_SetConfigBit(BNET_CONFIG_SPLIT_DAC_OUTPUT, enable);
}

int rp_BNetGetSplitDacOutput(bool* enable) {
    return bnet_GetConfigBit(BNET_CONFIG_SPLIT_DAC_OUTPUT, enable);
}

int rp_BNetSetCombineAdcInput(bool enable) {
    return bnet_SetConfigBit(BNET_CONFIG_COMBINE_ADC_INPUT, enable);
}

int rp_BNetGetCombineAdcInput(bool* enable) {
    return bnet_GetConfigBit(BNET_CONFIG_COMBINE_ADC_INPUT, enable);
}

int rp_BNetSetCombineAdcPhase(bool phase) {
    return bnet_SetConfigBit(BNET_CONFIG_COMBINE_ADC_PHASE, phase);
}

int rp_BNetGetCombineAdcPhase(bool* phase) {
    return bnet_GetConfigBit(BNET_CONFIG_COMBINE_ADC_PHASE, phase);
}

int rp_BNetSetVectorLength(uint32_t samples) {
    if (samples != 1024u && samples != 2048u && samples != 4096u)
        return RP_EOOR;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    bnet_WriteReg(BNET_VECTOR_LEN_OFFSET, samples);
    if (bnet_ReadRegSettled(BNET_VECTOR_LEN_OFFSET) != samples)
        return RP_EOP;
    return RP_OK;
}

int rp_BNetGetVectorLength(uint32_t* samples) {
    if (samples == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *samples = bnet_ReadRegSettled(BNET_VECTOR_LEN_OFFSET);
    return RP_OK;
}

int rp_BNetGetStreamCount(uint32_t* count) {
    if (count == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *count = bnet_ReadReg(BNET_STREAM_COUNT_OFFSET);
    return RP_OK;
}

int rp_BNetGetActiveMask(uint32_t* mask) {
    if (mask == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *mask = bnet_ReadReg(BNET_ACTIVE_MASK_OFFSET);
    return RP_OK;
}

int rp_BNetGetPendingMask(uint32_t* mask) {
    if (mask == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *mask = bnet_ReadReg(BNET_PENDING_MASK_OFFSET);
    return RP_OK;
}

int rp_BNetGetErrorMask(uint32_t* mask) {
    if (mask == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *mask = bnet_ReadReg(BNET_ERROR_MASK_OFFSET);
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

int rp_BNetSetWeightBank(uint32_t bank) {
    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    uint32_t vector_len = bnet_ReadRegSettled(BNET_VECTOR_LEN_OFFSET);
    if (vector_len == 4096u)
        return RP_EUF;
    if ((vector_len == 2048u && bank >= 2u) ||
        (vector_len == 1024u && bank >= 4u))
        return RP_EOOR;
    if (vector_len != 1024u && vector_len != 2048u)
        return RP_EIPV;

    bnet_WriteReg(BNET_WEIGHT_BANK_OFFSET, bank);
    uint32_t bank_status = bnet_ReadRegSettled(BNET_WEIGHT_BANK_OFFSET);
    if ((bank_status & BNET_WEIGHT_BANK_SELECTED) == 0 ||
        (bank_status & 0x3u) != bank)
        return RP_EOP;
    return RP_OK;
}

int rp_BNetGetWeightBank(uint32_t* bank) {
    if (bank == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *bank = bnet_ReadRegSettled(BNET_WEIGHT_BANK_OFFSET) & 0x3u;
    return RP_OK;
}

int rp_BNetGetWeightBankCount(uint32_t* count) {
    if (count == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    switch (bnet_ReadRegSettled(BNET_VECTOR_LEN_OFFSET)) {
        case 1024u: *count = 4u; return RP_OK;
        case 2048u: *count = 2u; return RP_OK;
        case 4096u: *count = 1u; return RP_OK;
        default: return RP_EIPV;
    }
}

int rp_BNetGetTiming(uint32_t index, uint32_t* cycles) {
    if (cycles == NULL)
        return RP_UIA;
    if (index > 5u)
        return RP_EOOR;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    const uint32_t offsets[6] = {
        BNET_TIME_TOTAL_OFFSET,
        BNET_TIME_LOAD_OFFSET,
        BNET_TIME_COMPUTE_OFFSET,
        BNET_TIME_PLAYBACK_OFFSET,
        BNET_TIME_INPUT_LOAD_OFFSET,
        BNET_TIME_LATENCY_OFFSET
    };
    *cycles = bnet_ReadReg(offsets[index]);
    return RP_OK;
}

int rp_BNetGetCaptureCount(uint32_t* count) {
    if (count == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *count = bnet_ReadReg(BNET_CAPTURE_COUNT_OFFSET);
    return RP_OK;
}

int rp_BNetGetCaptureStatus(uint32_t* status) {
    if (status == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *status = bnet_ReadReg(BNET_CAPTURE_STATUS_OFFSET);
    return RP_OK;
}

int rp_BNetGetCaptureData(uint32_t index, int32_t* value) {
    if (value == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    uint32_t count = bnet_ReadReg(BNET_CAPTURE_COUNT_OFFSET);
    if (index >= count)
        return RP_EOOR;

    *value = (int32_t)bnet_ReadCaptureSample(index);
    return RP_OK;
}

int rp_BNetGetCaptureDataBlock(uint32_t start, uint32_t samples, int16_t* values) {
    if (samples > 0 && values == NULL)
        return RP_UIA;

    int ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    uint32_t count = bnet_ReadReg(BNET_CAPTURE_COUNT_OFFSET);
    if (start > count || samples > (count - start))
        return RP_EOOR;

    for (uint32_t i = 0; i < samples; i++) {
        values[i] = bnet_ReadCaptureSample(start + i);
    }

    return RP_OK;
}

int rp_BNetSetStreamBase(uint32_t stream, uint32_t buffer, uint32_t address) {
    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;
    if (buffer > 1)
        return RP_EOOR;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    bnet_WriteReg(bnet_StreamRegOffset(stream, buffer == 0 ? BNET_STREAM_BASE0_OFFSET :
                                                        BNET_STREAM_BASE1_OFFSET),
                  address);
    return RP_OK;
}

int rp_BNetGetStreamBase(uint32_t stream, uint32_t buffer, uint32_t* address) {
    if (address == NULL)
        return RP_UIA;

    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;
    if (buffer > 1)
        return RP_EOOR;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *address = bnet_ReadReg(bnet_StreamRegOffset(stream, buffer == 0 ? BNET_STREAM_BASE0_OFFSET :
                                                                  BNET_STREAM_BASE1_OFFSET));
    return RP_OK;
}

int rp_BNetSetStreamLength(uint32_t stream, uint32_t bytes) {
    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    bnet_WriteReg(bnet_StreamRegOffset(stream, BNET_STREAM_LENGTH_OFFSET), bytes);
    return RP_OK;
}

int rp_BNetGetStreamLength(uint32_t stream, uint32_t* bytes) {
    if (bytes == NULL)
        return RP_UIA;

    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *bytes = bnet_ReadReg(bnet_StreamRegOffset(stream, BNET_STREAM_LENGTH_OFFSET));
    return RP_OK;
}

int rp_BNetSetStreamStride(uint32_t stream, uint32_t bytes) {
    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    bnet_WriteReg(bnet_StreamRegOffset(stream, BNET_STREAM_STRIDE_OFFSET), bytes);
    return RP_OK;
}

int rp_BNetGetStreamStride(uint32_t stream, uint32_t* bytes) {
    if (bytes == NULL)
        return RP_UIA;

    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *bytes = bnet_ReadReg(bnet_StreamRegOffset(stream, BNET_STREAM_STRIDE_OFFSET));
    return RP_OK;
}

int rp_BNetSetStreamFormat(uint32_t stream, uint32_t format) {
    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    bnet_WriteReg(bnet_StreamRegOffset(stream, BNET_STREAM_FORMAT_OFFSET), format);
    return RP_OK;
}

int rp_BNetGetStreamFormat(uint32_t stream, uint32_t* format) {
    if (format == NULL)
        return RP_UIA;

    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *format = bnet_ReadReg(bnet_StreamRegOffset(stream, BNET_STREAM_FORMAT_OFFSET));
    return RP_OK;
}

int rp_BNetEnableStream(uint32_t stream, bool enable) {
    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    bnet_WriteReg(bnet_StreamRegOffset(stream, BNET_STREAM_CONTROL_OFFSET),
                  enable ? BNET_STREAM_CONTROL_ENABLE : 0u);
    return RP_OK;
}

int rp_BNetGetStreamEnable(uint32_t stream, bool* enable) {
    if (enable == NULL)
        return RP_UIA;

    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *enable = bnet_GetStreamEnableBit(stream) != 0;
    return RP_OK;
}

int rp_BNetCommitStreamBuffer(uint32_t stream, uint32_t buffer) {
    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;
    if (buffer > 1)
        return RP_EOOR;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    uint32_t control = bnet_GetStreamEnableBit(stream);
    control |= (buffer == 0) ? BNET_STREAM_CONTROL_COMMIT_BUF0 :
                               BNET_STREAM_CONTROL_COMMIT_BUF1;
    bnet_WriteReg(bnet_StreamRegOffset(stream, BNET_STREAM_CONTROL_OFFSET), control);
    return RP_OK;
}

int rp_BNetForceStreamSwap(uint32_t stream) {
    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    uint32_t control = bnet_GetStreamEnableBit(stream) | BNET_STREAM_CONTROL_FORCE_SWAP;
    bnet_WriteReg(bnet_StreamRegOffset(stream, BNET_STREAM_CONTROL_OFFSET), control);
    return RP_OK;
}

int rp_BNetClearStreamError(uint32_t stream) {
    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    uint32_t control = bnet_GetStreamEnableBit(stream) | BNET_STREAM_CONTROL_CLEAR_ERROR;
    bnet_WriteReg(bnet_StreamRegOffset(stream, BNET_STREAM_CONTROL_OFFSET), control);
    return RP_OK;
}

int rp_BNetGetStreamStatus(uint32_t stream, uint32_t* status) {
    if (status == NULL)
        return RP_UIA;

    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *status = bnet_ReadReg(bnet_StreamRegOffset(stream, BNET_STREAM_STATUS_OFFSET));
    return RP_OK;
}

int rp_BNetGetStreamReadPtr(uint32_t stream, uint32_t* read_ptr) {
    if (read_ptr == NULL)
        return RP_UIA;

    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *read_ptr = bnet_ReadReg(bnet_StreamRegOffset(stream, BNET_STREAM_RPTR_OFFSET));
    return RP_OK;
}

int rp_BNetGetStreamDebug(uint32_t stream, uint32_t index, uint32_t* value) {
    if (value == NULL)
        return RP_UIA;
    if (index > 1u)
        return RP_UIA;

    int ret = bnet_CheckStream(stream);
    if (ret != RP_OK)
        return ret;

    ret = bnet_CheckMap();
    if (ret != RP_OK)
        return ret;

    *value = bnet_ReadReg(bnet_StreamRegOffset(stream,
                                               index == 0u ? BNET_STREAM_DBG0_OFFSET :
                                                             BNET_STREAM_DBG1_OFFSET));
    return RP_OK;
}

int rp_BNetDdrGetMemoryRegion(uint32_t* start, uint32_t* size) {
    if ((start == NULL) || (size == NULL))
        return RP_UIA;

    return axi_getOSReservedRegion(start, size);
}

int rp_BNetDdrReserve(uint32_t slot, uint32_t address, uint32_t size) {
    int ret = bnet_CheckDdrSlot(slot);
    if (ret != RP_OK)
        return ret;

    if (size == 0)
        return RP_EOOR;

    if (size % 0x80u) {
        ERROR_LOG("BNET DDR slot size must be a multiple of 0x80 bytes.")
        return RP_EOOR;
    }

    ECHECK(axi_initManager())

    if (bnet_ddr_slots[slot].index != 0) {
        axi_releaseMemory(bnet_ddr_slots[slot].index);
        bnet_ddr_slots[slot].index = 0;
        bnet_ddr_slots[slot].address = 0;
        bnet_ddr_slots[slot].size = 0;
    }

    uint64_t index = 0;
    ECHECK(axi_reserveMemory(address, size, &index))

    bnet_ddr_slots[slot].index = index;
    bnet_ddr_slots[slot].address = address;
    bnet_ddr_slots[slot].size = size;
    return RP_OK;
}

int rp_BNetDdrRelease(uint32_t slot) {
    int ret = bnet_CheckDdrSlot(slot);
    if (ret != RP_OK)
        return ret;

    if (bnet_ddr_slots[slot].index != 0)
        axi_releaseMemory(bnet_ddr_slots[slot].index);

    bnet_ddr_slots[slot].index = 0;
    bnet_ddr_slots[slot].address = 0;
    bnet_ddr_slots[slot].size = 0;
    return RP_OK;
}

int rp_BNetDdrGetSlotBase(uint32_t slot, uint32_t* address) {
    if (address == NULL)
        return RP_UIA;

    int ret = bnet_CheckDdrSlotReserved(slot);
    if (ret != RP_OK)
        return ret;

    *address = bnet_ddr_slots[slot].address;
    return RP_OK;
}

int rp_BNetDdrGetSlotSize(uint32_t slot, uint32_t* size) {
    if (size == NULL)
        return RP_UIA;

    int ret = bnet_CheckDdrSlotReserved(slot);
    if (ret != RP_OK)
        return ret;

    *size = bnet_ddr_slots[slot].size;
    return RP_OK;
}

int rp_BNetDdrAttachStreamBuffer(uint32_t slot, uint32_t stream, uint32_t buffer) {
    int ret = bnet_CheckDdrSlotReserved(slot);
    if (ret != RP_OK)
        return ret;

    ret = rp_BNetSetStreamBase(stream, buffer, bnet_ddr_slots[slot].address);
    if (ret != RP_OK)
        return ret;

    return rp_BNetSetStreamLength(stream, bnet_ddr_slots[slot].size);
}

int rp_BNetDdrWriteRaw(uint32_t slot, uint32_t offset_bytes, const uint8_t* data, uint32_t bytes) {
    if (data == NULL)
        return RP_UIA;

    int ret = bnet_CheckDdrSlotReserved(slot);
    if (ret != RP_OK)
        return ret;

    if ((bytes == 0) || (offset_bytes > bnet_ddr_slots[slot].size) ||
        (bytes > bnet_ddr_slots[slot].size - offset_bytes)) {
        return RP_EOOR;
    }

    uint16_t* buffer = NULL;
    uint32_t size = 0;
    ret = axi_getMapped(bnet_ddr_slots[slot].index, &buffer, &size);
    if (ret != RP_OK)
        return ret;

    if ((offset_bytes > size) || (bytes > size - offset_bytes))
        return RP_EOOR;

    memcpy((uint8_t*)buffer + offset_bytes, data, bytes);
    return RP_OK;
}

int rp_BNetDdrWriteI16(uint32_t slot, uint32_t offset_samples, const int16_t* data, uint32_t samples) {
    if ((offset_samples > UINT32_MAX / sizeof(int16_t)) ||
        (samples > UINT32_MAX / sizeof(int16_t))) {
        return RP_EOOR;
    }

    return rp_BNetDdrWriteRaw(slot, offset_samples * sizeof(int16_t),
                              (const uint8_t*)data, samples * sizeof(int16_t));
}

int rp_BNetDdrWriteU16(uint32_t slot, uint32_t offset_samples, const uint16_t* data, uint32_t samples) {
    if ((offset_samples > UINT32_MAX / sizeof(uint16_t)) ||
        (samples > UINT32_MAX / sizeof(uint16_t))) {
        return RP_EOOR;
    }

    return rp_BNetDdrWriteRaw(slot, offset_samples * sizeof(uint16_t),
                              (const uint8_t*)data, samples * sizeof(uint16_t));
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
