/**
 * @brief LVDS CARRY4 TDC API implementation.
 */

#include "tdc.h"
#include "common.h"
#include "rp.h"

#include <pthread.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/mman.h>

#define TDC_UIO_SLOT_OFFSET       0x00700000u
#define TDC_SLOT_SUBOFFSET        0x00010000u
#define TDC_MAP_SIZE              0x00011000u

#define TDC_ID_VERSION_OFFSET     0x00u
#define TDC_CONTROL_OFFSET        0x04u
#define TDC_STATUS_OFFSET         0x08u
#define TDC_LAUNCH_PERIOD_OFFSET  0x0cu
#define TDC_LAUNCH_WIDTH_OFFSET   0x10u
#define TDC_TIMEOUT_OFFSET        0x14u
#define TDC_NUM_TAPS_OFFSET       0x18u
#define TDC_CLOCK_PERIOD_OFFSET   0x1cu
#define TDC_LAST_COARSE_OFFSET    0x20u
#define TDC_LAST_FINE_RAW_OFFSET  0x24u
#define TDC_LAST_FINE_PS_OFFSET   0x28u
#define TDC_LAST_TOTAL_LO_OFFSET  0x2cu
#define TDC_LAST_TOTAL_HI_OFFSET  0x30u
#define TDC_LAST_STATUS_SEQ_OFFSET 0x34u
#define TDC_FIFO_LEVEL_OFFSET     0x38u
#define TDC_FIFO_SNAPSHOT0_OFFSET 0x3cu
#define TDC_FIFO_CONTROL_OFFSET   0x4cu
#define TDC_CAL_ADDR_OFFSET       0x50u
#define TDC_CAL_DATA_OFFSET       0x54u
#define TDC_CAL_CONTROL_OFFSET    0x58u
#define TDC_HIST_ADDR_OFFSET      0x5cu
#define TDC_HIST_DATA_OFFSET      0x60u
#define TDC_EVENT_COUNT_OFFSET    0x64u
#define TDC_RAW_WORD_ADDR_OFFSET  0x6cu
#define TDC_RAW_WORD_DATA_OFFSET  0x70u
#define TDC_CAL_TARGET_OFFSET     0x7cu
#define TDC_MMCM_CONTROL_OFFSET   0x80u
#define TDC_MMCM_STATUS_OFFSET    0x84u
#define TDC_MMCM_COARSE_DLY_OFFSET 0x88u
#define TDC_MMCM_PHASE_CNT_OFFSET 0x8cu
#define TDC_INPUT_SELECT_OFFSET   0x90u
#define TDC_WIDTH_ID              0x100u
#define TDC_WIDTH_COMMAND         0x104u
#define TDC_WIDTH_STATUS          0x108u
#define TDC_WIDTH_REQUEST_COUNT   0x10cu
#define TDC_WIDTH_CAPACITY        0x110u
#define TDC_WIDTH_COUNT           0x114u
#define TDC_WIDTH_INDEX           0x118u
#define TDC_WIDTH_RECORD          0x11cu
#define TDC_WIDTH_TICK            0x12cu
#define TDC_WIDTH_TIMEOUT         0x130u
#define TDC_WIDTH_PS              0x134u
#define TDC_WIDTH_LUT_ADDR         0x138u
#define TDC_WIDTH_LUT_DATA         0x13cu
#define TDC_WIDTH_LUT_CONTROL      0x140u
#define TDC_WIDTH_MIN_PERIOD       0x144u
#define TDC_WIDTH_READ_READY       0x148u // TDC v8+: index/width pipeline settled

#define TDC_WIDTH_DELAY_MIN        0x14cu // v13: ticks from launch to acceptance origin
#define TDC_WIDTH_DELAY_MAX        0x150u // v13: exclusive RISE deadline, launch-relative
#define TDC_WIDTH_LATENCY          0x154u // v13: selected record, coarse ticks, FFFF invalid

#define TDC_WIDTH_FRAME_OFFSET     0x158u // v14: frame shift in ns
#define TDC_WIDTH_FRAME_FEATURE    0x15cu // FRM v1 capability signature

#define TDC_ID_MASK               0xffffff00u
#define TDC_ID_EXPECTED           0x54444300u

#define TDC_CTRL_ENABLE           (1u << 0)
#define TDC_CTRL_TRIGGER          (1u << 1)
#define TDC_CTRL_CONTINUOUS       (1u << 2)
#define TDC_CTRL_RESET            (1u << 3)
#define TDC_CTRL_FIFO_CLEAR       (1u << 4)
#define TDC_CTRL_RAW_ENABLE       (1u << 5)
#define TDC_CTRL_HIST_ENABLE      (1u << 6)
#define TDC_CTRL_USE_LUT          (1u << 7)
#define TDC_CTRL_CAL_MODE         (1u << 9)
#define TDC_CTRL_INTERNAL_TEST    (1u << 10)
#define TDC_CTRL_MMCM_SWEEP       (1u << 11)

#define TDC_MMCM_CTRL_PS_REQUEST       (1u << 0)
#define TDC_MMCM_CTRL_PS_INCDEC        (1u << 1)
#define TDC_MMCM_CTRL_PHASE_CNT_CLEAR  (1u << 2)
#define TDC_MMCM_CTRL_RESET            (1u << 3)
#define TDC_MMCM_CTRL_TIMEOUT_CLEAR    (1u << 4)

#define TDC_MMCM_STATUS_LOCKED     (1u << 0)
#define TDC_MMCM_STATUS_PS_BUSY    (1u << 1)
#define TDC_MMCM_STATUS_PS_TIMEOUT (1u << 2)

#define TDC_MMCM_PS_POLL_ATTEMPTS 256u

#define TDC_FIFO_POP              (1u << 0)
#define TDC_CAL_WRITE             (1u << 0)
#define TDC_CAL_ACTIVATE          (1u << 1)
#define TDC_CAL_HIST_CLEAR        (1u << 2)
#define TDC_CAL_INACTIVE_READY    (1u << 3)
#define TDC_CAL_INVALIDATE        (1u << 3)

#define TDC_REGISTER_SETTLE_READS 16u

static void* tdc_mapping = NULL;
static volatile uint32_t* tdc_reg = NULL;
static pthread_mutex_t tdc_mutex = PTHREAD_MUTEX_INITIALIZER;

static inline void tdc_WriteReg(uint32_t offset, uint32_t value) {
    tdc_reg[offset / sizeof(uint32_t)] = value;
}

static inline uint32_t tdc_ReadReg(uint32_t offset) {
    return tdc_reg[offset / sizeof(uint32_t)];
}

static uint32_t tdc_ReadRegSettled(uint32_t offset) {
    uint32_t value = 0;
    for (uint32_t i = 0; i < TDC_REGISTER_SETTLE_READS; ++i)
        value = tdc_ReadReg(offset);
    return value;
}

static int tdc_CheckMap() {
    if (tdc_reg != NULL)
        return RP_OK;
    return tdc_Init();
}

static void tdc_UnpackResult(const uint32_t words[4], rp_tdc_result_t* result) {
    result->sequence_id = words[0] & 0xffffu;
    result->status = (words[0] >> 16) & 0xffu;
    result->coarse_cycles = (words[0] >> 24) | ((words[1] & 0x00ffffffu) << 8);
    result->fine_raw_index = (words[1] >> 24) | ((words[2] & 0x3u) << 8);
    result->fine_time_ps = (words[2] >> 2) & 0xffffu;
    result->total_time_ps = ((uint64_t)words[2] >> 18) | ((uint64_t)words[3] << 14);
    result->analogue_code = 0;
}

int tdc_Init() {
    if (tdc_reg != NULL)
        return RP_OK;

    int result = cmn_Map(TDC_MAP_SIZE, TDC_UIO_SLOT_OFFSET, &tdc_mapping);
    if (result != RP_OK)
        return result;
    // cmn_Map() in this tree checks the address of its output argument rather
    // than the mmap result itself, so guard this optional block locally.
    if (tdc_mapping == MAP_FAILED) {
        tdc_mapping = NULL;
        return RP_EMMD;
    }

    tdc_reg = (volatile uint32_t*)((uint8_t*)tdc_mapping + TDC_SLOT_SUBOFFSET);
    if ((tdc_ReadRegSettled(TDC_ID_VERSION_OFFSET) & TDC_ID_MASK) != TDC_ID_EXPECTED) {
        tdc_reg = NULL;
        cmn_Unmap(TDC_MAP_SIZE, &tdc_mapping);
        tdc_mapping = NULL;
        return RP_EUF;
    }
    return RP_OK;
}

int tdc_Release() {
    if (tdc_mapping == NULL) {
        tdc_reg = NULL;
        return RP_OK;
    }
    tdc_reg = NULL;
    int result = cmn_Unmap(TDC_MAP_SIZE, &tdc_mapping);
    tdc_mapping = NULL;
    return result;
}

static int tdc_UpdateControl(uint32_t clear_mask, uint32_t set_mask) {
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    uint32_t control = tdc_ReadRegSettled(TDC_CONTROL_OFFSET);
    control = (control & ~clear_mask) | set_mask;
    tdc_WriteReg(TDC_CONTROL_OFFSET, control);
    return RP_OK;
}

int rp_TdcReset(void) {
    return tdc_UpdateControl(0u, TDC_CTRL_RESET | TDC_CTRL_FIFO_CLEAR);
}

int rp_TdcEnable(bool enable) {
    return tdc_UpdateControl(TDC_CTRL_ENABLE, enable ? TDC_CTRL_ENABLE : 0u);
}

int rp_TdcGetEnable(bool* enable) {
    if (enable == NULL)
        return RP_UIA;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    *enable = (tdc_ReadReg(TDC_CONTROL_OFFSET) & TDC_CTRL_ENABLE) != 0;
    return RP_OK;
}

int rp_TdcSetMode(rp_tdc_mode_t mode) {
    if (mode < RP_TDC_MODE_SINGLE || mode > RP_TDC_MODE_CALIBRATION)
        return RP_EOOR;
    uint32_t set = 0;
    if (mode == RP_TDC_MODE_CONTINUOUS)
        set = TDC_CTRL_CONTINUOUS;
    else if (mode == RP_TDC_MODE_CALIBRATION)
        set = TDC_CTRL_CAL_MODE | TDC_CTRL_HIST_ENABLE | TDC_CTRL_RAW_ENABLE;
    return tdc_UpdateControl(TDC_CTRL_CONTINUOUS | TDC_CTRL_CAL_MODE |
                             TDC_CTRL_HIST_ENABLE | TDC_CTRL_RAW_ENABLE, set);
}

int rp_TdcGetMode(rp_tdc_mode_t* mode) {
    if (mode == NULL)
        return RP_UIA;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    uint32_t control = tdc_ReadReg(TDC_CONTROL_OFFSET);
    *mode = (control & TDC_CTRL_CAL_MODE) ? RP_TDC_MODE_CALIBRATION :
            (control & TDC_CTRL_CONTINUOUS) ? RP_TDC_MODE_CONTINUOUS :
                                             RP_TDC_MODE_SINGLE;
    return RP_OK;
}

static int tdc_CheckInputFeature() {
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    uint32_t id = tdc_ReadRegSettled(TDC_ID_VERSION_OFFSET);
    return ((id & TDC_ID_MASK) == TDC_ID_EXPECTED && (id & 0xffu) >= 4u)
           ? RP_OK : RP_EUF;
}

int rp_TdcSetInput(rp_tdc_input_t input) {
    if (input != RP_TDC_INPUT_LVDS && input != RP_TDC_INPUT_SINGLE)
        return RP_EOOR;
    int result = tdc_CheckInputFeature();
    if (result != RP_OK)
        return result;
    if ((tdc_ReadRegSettled(TDC_CONTROL_OFFSET) & TDC_CTRL_ENABLE) ||
        (tdc_ReadRegSettled(TDC_STATUS_OFFSET) & RP_TDC_STATUS_BUSY))
        return RP_EIPV;
    tdc_WriteReg(TDC_INPUT_SELECT_OFFSET, (uint32_t)input);
    // The RTL also rejects live changes, including a race with another writer.
    return tdc_ReadRegSettled(TDC_INPUT_SELECT_OFFSET) == (uint32_t)input
           ? RP_OK : RP_EIPV;
}

int rp_TdcGetInput(rp_tdc_input_t* input) {
    if (input == NULL)
        return RP_UIA;
    int result = tdc_CheckInputFeature();
    if (result != RP_OK)
        return result;
    uint32_t value = tdc_ReadRegSettled(TDC_INPUT_SELECT_OFFSET);
    if (value > RP_TDC_INPUT_SINGLE)
        return RP_EIPV;
    *input = (rp_tdc_input_t)value;
    return RP_OK;
}

static int tdc_CheckWidth() {
    int result = tdc_CheckMap();
    if (result != RP_OK) return result;
    uint32_t id = tdc_ReadRegSettled(TDC_ID_VERSION_OFFSET);
    if ((id & TDC_ID_MASK) != TDC_ID_EXPECTED || (id & 0xffu) < 5u)
        return RP_EUF;
    return tdc_ReadRegSettled(TDC_WIDTH_ID) == 0x50574201u ? RP_OK : RP_EUF;
}

static int tdc_WidthIdle() {
    int result = tdc_CheckWidth();
    if (result != RP_OK) return result;
    return (tdc_ReadRegSettled(TDC_WIDTH_STATUS) & RP_TDC_WIDTH_BUSY) ? RP_EIPV : RP_OK;
}

static int tdc_WidthValue(uint32_t offset, uint32_t* value) {
    if (value == NULL) return RP_UIA;
    int result = tdc_CheckWidth();
    if (result != RP_OK) return result;
    *value = tdc_ReadRegSettled(offset);
    return RP_OK;
}
int rp_TdcWidthGetStatus(uint32_t* v) { return tdc_WidthValue(TDC_WIDTH_STATUS, v); }
int rp_TdcWidthGetCount(uint32_t* v) { return tdc_WidthValue(TDC_WIDTH_COUNT, v); }
int rp_TdcWidthGetCapacity(uint32_t* v) { return tdc_WidthValue(TDC_WIDTH_CAPACITY, v); }
int rp_TdcWidthGetTick(uint32_t* v) { return tdc_WidthValue(TDC_WIDTH_TICK, v); }
int rp_TdcWidthGetTimeout(uint32_t* v) { return tdc_WidthValue(TDC_WIDTH_TIMEOUT, v); }

// Bounds are stored in fast-clock ticks, independent of the pulse period.
// The rise window must fit inside one period; the FALL may spill into the next.
static int tdc_CheckReturnTiming() {
    int result = tdc_CheckWidth();
    if (result != RP_OK) return result;
    return (tdc_ReadRegSettled(TDC_ID_VERSION_OFFSET) & 0xffu) == 13u ? RP_OK : RP_EUF;
}

int rp_TdcWidthSetDelay(uint32_t minimum_ns, uint32_t maximum_ns) {
    if (minimum_ns % 4u || maximum_ns % 4u || maximum_ns <= minimum_ns ||
        maximum_ns > 65534u * 4u) return RP_EOOR;
    pthread_mutex_lock(&tdc_mutex);
    int result = tdc_CheckReturnTiming();
    if (result == RP_OK) result = tdc_WidthIdle();
    if (result == RP_OK) {
        tdc_WriteReg(TDC_WIDTH_DELAY_MIN, minimum_ns / 4u);
        tdc_WriteReg(TDC_WIDTH_DELAY_MAX, maximum_ns / 4u);
        if (tdc_ReadRegSettled(TDC_WIDTH_DELAY_MIN) != minimum_ns / 4u ||
            tdc_ReadRegSettled(TDC_WIDTH_DELAY_MAX) != maximum_ns / 4u) result = RP_EIPV;
    }
    pthread_mutex_unlock(&tdc_mutex);
    return result;
}

int rp_TdcWidthGetDelay(uint32_t* minimum_ns, uint32_t* maximum_ns) {
    if (!minimum_ns || !maximum_ns) return RP_UIA;
    pthread_mutex_lock(&tdc_mutex);
    int result = tdc_CheckReturnTiming();
    if (result == RP_OK) {
        *minimum_ns = tdc_ReadRegSettled(TDC_WIDTH_DELAY_MIN) * 4u;
        *maximum_ns = tdc_ReadRegSettled(TDC_WIDTH_DELAY_MAX) * 4u;
    }
    pthread_mutex_unlock(&tdc_mutex);
    return result;
}

int rp_TdcWidthReadLatency(uint32_t start, uint32_t* ticks, uint32_t count) {
    if (!ticks && count) return RP_UIA;
    pthread_mutex_lock(&tdc_mutex);
    int result = tdc_CheckReturnTiming();
    if (result == RP_OK) result = tdc_WidthIdle();
    if (result == RP_OK) {
        const uint32_t available = tdc_ReadRegSettled(TDC_WIDTH_COUNT);
        if (start > available || count > available-start) result = RP_EOOR;
    }
    for (uint32_t i=0; result==RP_OK && i<count; ++i) {
        tdc_WriteReg(TDC_WIDTH_INDEX,start+i);
        bool ready=false;
        for (unsigned attempt=0; attempt<64u; ++attempt) {
            if (tdc_ReadRegSettled(TDC_WIDTH_READ_READY) & 1u) { ready=true; break; }
        }
        if (!ready) { result=RP_EUF; break; }
        ticks[i]=tdc_ReadRegSettled(TDC_WIDTH_LATENCY);
        if (ticks[i]>65535u) result=RP_EUF;
    }
    pthread_mutex_unlock(&tdc_mutex);
    return result;
}

static int tdc_CheckFrameOffset() {
    int result = tdc_CheckWidth();
    if (result != RP_OK) return result;
    if ((tdc_ReadRegSettled(TDC_ID_VERSION_OFFSET) & 0xffu) < 14u) return RP_EUF;
    return tdc_ReadRegSettled(TDC_WIDTH_FRAME_FEATURE) == 0x46524d01u ? RP_OK : RP_EUF;
}

int rp_TdcWidthSetFrameOffset(uint32_t nanoseconds) {
    if (nanoseconds % 4u || nanoseconds > 262140u) return RP_EOOR;
    pthread_mutex_lock(&tdc_mutex);
    int result = tdc_CheckFrameOffset();
    if (result == RP_OK) result = tdc_WidthIdle();
    uint64_t period=0,high=0;
    if (result == RP_OK) result = rp_PulseGetTiming(&period,&high);
    if (result == RP_OK && nanoseconds >= period) result = RP_EOOR;
    if (result == RP_OK) {
        tdc_WriteReg(TDC_WIDTH_FRAME_OFFSET,nanoseconds);
        if (tdc_ReadRegSettled(TDC_WIDTH_FRAME_OFFSET) != nanoseconds) result = RP_EIPV;
    }
    pthread_mutex_unlock(&tdc_mutex);
    return result;
}

int rp_TdcWidthGetFrameOffset(uint32_t* nanoseconds) {
    if (!nanoseconds) return RP_UIA;
    pthread_mutex_lock(&tdc_mutex);
    int result = tdc_CheckFrameOffset();
    if (result == RP_OK) *nanoseconds = tdc_ReadRegSettled(TDC_WIDTH_FRAME_OFFSET);
    pthread_mutex_unlock(&tdc_mutex);
    return result;
}

int rp_TdcWidthArm(uint32_t count) {
    int result = tdc_WidthIdle();
    if (result != RP_OK) return result;
    if (count == 0 || count > tdc_ReadRegSettled(TDC_WIDTH_CAPACITY)) return RP_EOOR;
    if ((tdc_ReadRegSettled(TDC_CONTROL_OFFSET) &
         (TDC_CTRL_ENABLE | TDC_CTRL_INTERNAL_TEST | TDC_CTRL_MMCM_SWEEP)) ||
        (tdc_ReadRegSettled(TDC_STATUS_OFFSET) & RP_TDC_STATUS_BUSY)) return RP_EIPV;
    uint64_t period = 0, high = 0;
    result = rp_PulseGetTiming(&period, &high);
    if (result != RP_OK) return result;
    if (period < tdc_ReadRegSettled(TDC_WIDTH_MIN_PERIOD) || high * 2u != period)
        return RP_EOOR;
    bool pulse_enabled = false;
    result = rp_PulseGetEnabled(&pulse_enabled);
    if (result != RP_OK) return result;
    if (!pulse_enabled) return RP_EIPV;
    if ((tdc_ReadRegSettled(TDC_ID_VERSION_OFFSET) & 0xffu) == 13u) {
        const uint32_t lo=tdc_ReadRegSettled(TDC_WIDTH_DELAY_MIN);
        const uint32_t hi=tdc_ReadRegSettled(TDC_WIDTH_DELAY_MAX);
        if (hi<=lo || (uint64_t)(hi-lo)*4u>period) return RP_EOOR;
    }
    if ((tdc_ReadRegSettled(TDC_ID_VERSION_OFFSET) & 0xffu) >= 14u) {
        result = tdc_CheckFrameOffset();
        if (result != RP_OK) return result;
        const uint32_t shift=tdc_ReadRegSettled(TDC_WIDTH_FRAME_OFFSET);
        if (shift % 4u || shift > 262140u || shift >= period) return RP_EOOR;
    }
    // Allow two periods for starting/stopped-trigger watchdog, with margin.
    uint64_t timeout = period / 2u + 32u; // 2*period / 4 ns
    if (timeout > UINT32_MAX) return RP_EOOR;
    pthread_mutex_lock(&tdc_mutex);
    result = tdc_WidthIdle();
    if (result == RP_OK) {
        tdc_WriteReg(TDC_WIDTH_TIMEOUT, (uint32_t)timeout);
        tdc_WriteReg(TDC_WIDTH_REQUEST_COUNT, count);
        tdc_WriteReg(TDC_WIDTH_COMMAND, 1u);
    }
    pthread_mutex_unlock(&tdc_mutex);
    return result;
}

int rp_TdcWidthAbort(void) {
    int result = tdc_CheckWidth();
    if (result == RP_OK) tdc_WriteReg(TDC_WIDTH_COMMAND, 2u);
    return result;
}

int rp_TdcWidthClear(void) {
    int result = tdc_WidthIdle();
    if (result == RP_OK) tdc_WriteReg(TDC_WIDTH_COMMAND, 4u);
    return result;
}

int rp_TdcWidthSetTimeout(uint32_t cycles) {
    if (cycles == 0) return RP_EOOR;
    int result = tdc_WidthIdle();
    if (result == RP_OK) tdc_WriteReg(TDC_WIDTH_TIMEOUT, cycles);
    return result;
}

int rp_TdcWidthGetVersion(uint32_t* version) {
    if (version == NULL) return RP_UIA;
    int result = tdc_CheckWidth();
    if (result == RP_OK) *version = tdc_ReadRegSettled(TDC_ID_VERSION_OFFSET) & 0xffu;
    return result;
}

static bool tdc_WidthRecordConsistent(const rp_tdc_width_result_t& r,
                                    uint32_t expected_cycle, uint32_t taps) {
    if (r.cycle_id != expected_cycle || r.rise_raw >= taps || r.fall_raw >= taps)
        return false;
    if (!(r.flags & RP_TDC_WIDTH_VALID)) return r.width_ps == 0;
    const uint32_t frame_errors = RP_TDC_WIDTH_NO_RISE | RP_TDC_WIDTH_NO_FALL |
        RP_TDC_WIDTH_HIGH_AT_START | RP_TDC_WIDTH_EXTRA_EDGES |
        RP_TDC_WIDTH_TRIGGER_TIMEOUT | RP_TDC_WIDTH_BOUNDARY |
        RP_TDC_WIDTH_SATURATED | RP_TDC_WIDTH_OUT_OF_RANGE | RP_TDC_WIDTH_RETURN_LATE;
    if (r.flags & frame_errors) return false;
    const uint32_t mode = r.flags & (RP_TDC_WIDTH_COARSE_ONLY | RP_TDC_WIDTH_CALIBRATED);
    if (mode != RP_TDC_WIDTH_COARSE_ONLY && mode != RP_TDC_WIDTH_CALIBRATED)
        return false;
    const bool fine_valid = ((r.flags >> 16) & 1u) && ((r.flags >> 24) & 1u);
    const bool fine_invalid = (r.flags & RP_TDC_WIDTH_FINE_INVALID) != 0;
    if (fine_invalid != !fine_valid) return false;
    const uint64_t coarse_ps = (uint64_t)r.coarse_ticks * 4000u;
    if (coarse_ps > UINT32_MAX) return false;
    if (mode == RP_TDC_WIDTH_COARSE_ONLY) return r.width_ps == coarse_ps;
    // The stored correction is a difference of two unsigned 16-bit LUT values.
    const int64_t correction = (int64_t)r.width_ps - (int64_t)coarse_ps;
    return fine_valid && correction >= -65535 && correction <= 65535;
}

static int tdc_WidthReadImpl(uint32_t start, rp_tdc_width_result_t* values,
                             uint32_t count, bool check_records) {
    if (values == NULL && count) return RP_UIA;
    pthread_mutex_lock(&tdc_mutex);
    int result = tdc_WidthIdle();
    uint32_t version = 0, taps = 0;
    if (result == RP_OK) {
        uint32_t available = tdc_ReadRegSettled(TDC_WIDTH_COUNT);
        if (start > available || count > available - start) result = RP_EOOR;
        version = tdc_ReadRegSettled(TDC_ID_VERSION_OFFSET) & 0xffu;
        if (check_records) taps = tdc_ReadRegSettled(TDC_NUM_TAPS_OFFSET);
    }
    for (uint32_t i = 0; result == RP_OK && i < count; ++i) {
        tdc_WriteReg(TDC_WIDTH_INDEX, start + i);
        // Older images use the conservative settling reads. New images
        // explicitly report that all bank/multiply/correction stages settled.
        if (version >= 8u) {
            bool ready = false;
            for (unsigned attempt = 0; attempt < 64u; ++attempt) {
                if (tdc_ReadRegSettled(TDC_WIDTH_READ_READY) & 1u) { ready = true; break; }
            }
            if (!ready) { result = RP_EUF; break; }
        } else (void)tdc_ReadRegSettled(TDC_WIDTH_INDEX);
        values[i].cycle_id = tdc_ReadRegSettled(TDC_WIDTH_RECORD);
        values[i].flags = tdc_ReadRegSettled(TDC_WIDTH_RECORD + 4u);
        values[i].coarse_ticks = tdc_ReadRegSettled(TDC_WIDTH_RECORD + 8u);
        uint32_t raw = tdc_ReadRegSettled(TDC_WIDTH_RECORD + 12u);
        values[i].rise_raw = raw & 0xffffu;
        values[i].fall_raw = raw >> 16;
        values[i].width_ps = tdc_ReadRegSettled(TDC_WIDTH_PS);
        // Never repair flags, interpolate, retry until plausible, or silently
        // drop a corrupted record. A separate raw API preserves diagnostics.
        if (check_records && !tdc_WidthRecordConsistent(values[i], start + i + 1u, taps))
            result = RP_EUF;
    }
    pthread_mutex_unlock(&tdc_mutex);
    return result;
}

int rp_TdcWidthRead(uint32_t start, rp_tdc_width_result_t* values, uint32_t count) {
    return tdc_WidthReadImpl(start, values, count, true);
}

int rp_TdcWidthReadRaw(uint32_t start, rp_tdc_width_result_t* values, uint32_t count) {
    return tdc_WidthReadImpl(start, values, count, false);
}

static int tdc_WidthLut(bool falling, uint32_t start, uint16_t* values,
                         const uint16_t* write_values, uint32_t count) {
    pthread_mutex_lock(&tdc_mutex);
    int result = tdc_WidthIdle();
    uint32_t taps = result == RP_OK ? tdc_ReadRegSettled(TDC_NUM_TAPS_OFFSET) : 0;
    if (result == RP_OK && (start > taps || count > taps - start)) result = RP_EOOR;
    for (uint32_t i = 0; result == RP_OK && i < count; ++i) {
        tdc_WriteReg(TDC_WIDTH_LUT_ADDR, (falling ? taps : 0u) + start + i);
        if (write_values) tdc_WriteReg(TDC_WIDTH_LUT_DATA, write_values[i]);
        else values[i] = (uint16_t)tdc_ReadRegSettled(TDC_WIDTH_LUT_DATA);
    }
    pthread_mutex_unlock(&tdc_mutex);
    return result;
}
int rp_TdcWidthWriteLut(bool fall, uint32_t start, const uint16_t* v, uint32_t count) {
    if (v == NULL && count) return RP_UIA;
    return tdc_WidthLut(fall, start, NULL, v, count);
}
int rp_TdcWidthReadLut(bool fall, uint32_t start, uint16_t* v, uint32_t count) {
    if (v == NULL && count) return RP_UIA;
    return tdc_WidthLut(fall, start, v, NULL, count);
}
int rp_TdcWidthActivateCalibration(bool enable) {
    int result = tdc_WidthIdle();
    if (result != RP_OK) return result;
    if (enable && !(tdc_ReadRegSettled(TDC_WIDTH_LUT_CONTROL) & 4u)) return RP_EIPV;
    tdc_WriteReg(TDC_WIDTH_LUT_CONTROL, enable ? 2u : 4u);
    return !!(tdc_ReadRegSettled(TDC_WIDTH_LUT_CONTROL) & 1u) == enable ? RP_OK : RP_EIPV;
}
int rp_TdcWidthGetCalibration(bool* enable) {
    if (enable == NULL) return RP_UIA;
    uint32_t value = 0;
    int result = tdc_WidthValue(TDC_WIDTH_LUT_CONTROL, &value);
    if (result == RP_OK) *enable = (value & 1u) != 0;
    return result;
}

static int tdc_SetNonzero(uint32_t offset, uint32_t value) {
    if (value == 0)
        return RP_EOOR;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    tdc_WriteReg(offset, value);
    return RP_OK;
}

static int tdc_GetValue(uint32_t offset, uint32_t* value) {
    if (value == NULL)
        return RP_UIA;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    *value = tdc_ReadReg(offset);
    return RP_OK;
}

int rp_TdcSetLaunchPeriod(uint32_t cycles) { return tdc_SetNonzero(TDC_LAUNCH_PERIOD_OFFSET, cycles); }
int rp_TdcGetLaunchPeriod(uint32_t* cycles) { return tdc_GetValue(TDC_LAUNCH_PERIOD_OFFSET, cycles); }
int rp_TdcSetLaunchWidth(uint32_t cycles) { return tdc_SetNonzero(TDC_LAUNCH_WIDTH_OFFSET, cycles); }
int rp_TdcGetLaunchWidth(uint32_t* cycles) { return tdc_GetValue(TDC_LAUNCH_WIDTH_OFFSET, cycles); }
int rp_TdcSetTimeout(uint32_t cycles) { return tdc_SetNonzero(TDC_TIMEOUT_OFFSET, cycles); }
int rp_TdcGetTimeout(uint32_t* cycles) { return tdc_GetValue(TDC_TIMEOUT_OFFSET, cycles); }

int rp_TdcTrigger(void) {
    return tdc_UpdateControl(0u, TDC_CTRL_TRIGGER);
}

int rp_TdcGetStatus(uint32_t* status) { return tdc_GetValue(TDC_STATUS_OFFSET, status); }
int rp_TdcGetFifoLevel(uint32_t* level) { return tdc_GetValue(TDC_FIFO_LEVEL_OFFSET, level); }
int rp_TdcGetNumTaps(uint32_t* taps) { return tdc_GetValue(TDC_NUM_TAPS_OFFSET, taps); }

int rp_TdcSetInternalTest(bool enable) {
    return tdc_UpdateControl(TDC_CTRL_INTERNAL_TEST,
                             enable ? TDC_CTRL_INTERNAL_TEST : 0u);
}

int rp_TdcGetInternalTest(bool* enable) {
    if (enable == NULL)
        return RP_UIA;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    *enable = (tdc_ReadRegSettled(TDC_CONTROL_OFFSET) & TDC_CTRL_INTERNAL_TEST) != 0;
    return RP_OK;
}

int rp_TdcMmcmSetSweepEnable(bool enable) {
    return tdc_UpdateControl(TDC_CTRL_MMCM_SWEEP,
                             enable ? TDC_CTRL_MMCM_SWEEP : 0u);
}

int rp_TdcMmcmGetSweepEnable(bool* enable) {
    if (enable == NULL)
        return RP_UIA;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    *enable = (tdc_ReadRegSettled(TDC_CONTROL_OFFSET) & TDC_CTRL_MMCM_SWEEP) != 0;
    return RP_OK;
}

int rp_TdcMmcmReset(void) {
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    tdc_WriteReg(TDC_MMCM_CONTROL_OFFSET, TDC_MMCM_CTRL_RESET);
    return RP_OK;
}

int rp_TdcMmcmSetCoarseDelay(uint16_t cycles) {
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    tdc_WriteReg(TDC_MMCM_COARSE_DLY_OFFSET, cycles);
    return RP_OK;
}

int rp_TdcMmcmGetCoarseDelay(uint16_t* cycles) {
    if (cycles == NULL)
        return RP_UIA;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    *cycles = (uint16_t)tdc_ReadReg(TDC_MMCM_COARSE_DLY_OFFSET);
    return RP_OK;
}

int rp_TdcMmcmGetStatus(uint32_t* status) {
    return tdc_GetValue(TDC_MMCM_STATUS_OFFSET, status);
}

int rp_TdcMmcmClearTimeout(void) {
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    tdc_WriteReg(TDC_MMCM_CONTROL_OFFSET, TDC_MMCM_CTRL_TIMEOUT_CLEAR);
    return RP_OK;
}

int rp_TdcMmcmGetPhaseCount(int32_t* count) {
    if (count == NULL)
        return RP_UIA;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    *count = (int32_t)tdc_ReadReg(TDC_MMCM_PHASE_CNT_OFFSET);
    return RP_OK;
}

int rp_TdcMmcmClearPhaseCount(void) {
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    tdc_WriteReg(TDC_MMCM_CONTROL_OFFSET, TDC_MMCM_CTRL_PHASE_CNT_CLEAR);
    return RP_OK;
}

int rp_TdcMmcmPhaseStep(bool increase) {
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;

    pthread_mutex_lock(&tdc_mutex);
    if (tdc_ReadRegSettled(TDC_MMCM_STATUS_OFFSET) & TDC_MMCM_STATUS_PS_BUSY) {
        pthread_mutex_unlock(&tdc_mutex);
        return RP_EUF;
    }
    if (!(tdc_ReadReg(TDC_MMCM_STATUS_OFFSET) & TDC_MMCM_STATUS_LOCKED)) {
        pthread_mutex_unlock(&tdc_mutex);
        return RP_EIPV;
    }

    uint32_t command = TDC_MMCM_CTRL_PS_REQUEST |
                        (increase ? TDC_MMCM_CTRL_PS_INCDEC : 0u);
    tdc_WriteReg(TDC_MMCM_CONTROL_OFFSET, command);

    // The FPGA watchdog aborts an un-acknowledged phase-shift request after a
    // bounded number of clk_i cycles; poll register reads comfortably span
    // that window because each crosses the full sys-bus round trip.
    bool busy = true;
    for (uint32_t i = 0; i < TDC_MMCM_PS_POLL_ATTEMPTS && busy; ++i)
        busy = (tdc_ReadReg(TDC_MMCM_STATUS_OFFSET) & TDC_MMCM_STATUS_PS_BUSY) != 0;

    uint32_t status = tdc_ReadRegSettled(TDC_MMCM_STATUS_OFFSET);
    pthread_mutex_unlock(&tdc_mutex);

    if (busy)
        return RP_EUF;
    if (status & TDC_MMCM_STATUS_PS_TIMEOUT)
        return RP_EUF;
    return RP_OK;
}

int rp_TdcReadResult(rp_tdc_result_t* result) {
    if (result == NULL)
        return RP_UIA;
    int status = tdc_CheckMap();
    if (status != RP_OK)
        return status;

    pthread_mutex_lock(&tdc_mutex);
    if (tdc_ReadReg(TDC_FIFO_LEVEL_OFFSET) == 0) {
        pthread_mutex_unlock(&tdc_mutex);
        return RP_EUF;
    }

    tdc_WriteReg(TDC_FIFO_CONTROL_OFFSET, TDC_FIFO_POP);
    // The register pulse and FIFO snapshot cross the existing sys_bus CDC.
    // Repeated dependent reads keep the transaction ordered until the pop has
    // reached the adc_clk-domain FIFO and its snapshot register is stable.
    (void)tdc_ReadRegSettled(TDC_FIFO_LEVEL_OFFSET);
    uint32_t words[4];
    for (uint32_t i = 0; i < 4; ++i)
        words[i] = tdc_ReadReg(TDC_FIFO_SNAPSHOT0_OFFSET + i * sizeof(uint32_t));
    tdc_UnpackResult(words, result);
    pthread_mutex_unlock(&tdc_mutex);
    return RP_OK;
}

int rp_TdcGetLastResult(rp_tdc_result_t* result) {
    if (result == NULL)
        return RP_UIA;
    int status = tdc_CheckMap();
    if (status != RP_OK)
        return status;

    pthread_mutex_lock(&tdc_mutex);
    uint32_t marker_before = 0;
    uint32_t marker_after = 0;
    do {
        marker_before = tdc_ReadReg(TDC_LAST_STATUS_SEQ_OFFSET);
        result->coarse_cycles = tdc_ReadReg(TDC_LAST_COARSE_OFFSET);
        result->fine_raw_index = tdc_ReadReg(TDC_LAST_FINE_RAW_OFFSET);
        result->fine_time_ps = tdc_ReadReg(TDC_LAST_FINE_PS_OFFSET);
        uint64_t total_lo = tdc_ReadReg(TDC_LAST_TOTAL_LO_OFFSET);
        uint64_t total_hi = tdc_ReadReg(TDC_LAST_TOTAL_HI_OFFSET) & 0x3fffu;
        result->total_time_ps = total_lo | (total_hi << 32);
        marker_after = tdc_ReadReg(TDC_LAST_STATUS_SEQ_OFFSET);
    } while (marker_before != marker_after);
    result->sequence_id = marker_after >> 16;
    result->status = marker_after & 0xffu;
    result->analogue_code = 0;
    pthread_mutex_unlock(&tdc_mutex);
    return RP_OK;
}

int rp_TdcGetRawCapture(uint32_t start_word, uint32_t* words, uint32_t count) {
    if (count > 0 && words == NULL)
        return RP_UIA;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    uint32_t taps = tdc_ReadReg(TDC_NUM_TAPS_OFFSET);
    uint32_t total_words = (taps + 31u) / 32u;
    if (start_word > total_words || count > total_words - start_word)
        return RP_EOOR;
    for (uint32_t i = 0; i < count; ++i) {
        tdc_WriteReg(TDC_RAW_WORD_ADDR_OFFSET, start_word + i);
        words[i] = tdc_ReadRegSettled(TDC_RAW_WORD_DATA_OFFSET);
    }
    return RP_OK;
}

int rp_TdcCalibrationClearHistogram(void) {
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    tdc_WriteReg(TDC_CAL_CONTROL_OFFSET, TDC_CAL_HIST_CLEAR);
    return RP_OK;
}

int rp_TdcCalibrationStart(uint32_t target_events) {
    if (target_events == 0)
        return RP_EOOR;
    int result = rp_TdcReset();
    if (result != RP_OK)
        return result;
    result = rp_TdcCalibrationClearHistogram();
    if (result != RP_OK)
        return result;
    result = rp_TdcSetMode(RP_TDC_MODE_CALIBRATION);
    if (result != RP_OK)
        return result;
    tdc_WriteReg(TDC_CAL_TARGET_OFFSET, target_events);
    return rp_TdcEnable(true);
}

int rp_TdcCalibrationStop(void) { return rp_TdcEnable(false); }

int rp_TdcCalibrationGetStatus(uint32_t* status, uint32_t* events_collected) {
    if (status == NULL || events_collected == NULL)
        return RP_UIA;
    int result = rp_TdcGetStatus(status);
    if (result != RP_OK)
        return result;
    return tdc_GetValue(TDC_EVENT_COUNT_OFFSET, events_collected);
}

int rp_TdcCalibrationReadHistogram(uint32_t start_bin, uint32_t* counts, uint32_t count) {
    if (count > 0 && counts == NULL)
        return RP_UIA;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    uint32_t taps = tdc_ReadReg(TDC_NUM_TAPS_OFFSET);
    if (start_bin > taps || count > taps - start_bin)
        return RP_EOOR;
    for (uint32_t i = 0; i < count; ++i) {
        tdc_WriteReg(TDC_HIST_ADDR_OFFSET, start_bin + i);
        counts[i] = tdc_ReadRegSettled(TDC_HIST_DATA_OFFSET);
    }
    return RP_OK;
}

int rp_TdcCalibrationWriteLut(uint32_t start_bin, const uint16_t* time_ps, uint32_t count) {
    if (count > 0 && time_ps == NULL)
        return RP_UIA;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    uint32_t taps = tdc_ReadReg(TDC_NUM_TAPS_OFFSET);
    if (start_bin > taps || count > taps - start_bin)
        return RP_EOOR;
    // Starting at bin zero begins a new inactive-bank image.  Later ranged
    // writes can append to it; activation remains locked until every bin was
    // written at least once.
    if (start_bin == 0) {
        tdc_WriteReg(TDC_CAL_CONTROL_OFFSET, TDC_CAL_INVALIDATE);
        (void)tdc_ReadRegSettled(TDC_CAL_CONTROL_OFFSET);
    }
    for (uint32_t i = 0; i < count; ++i) {
        tdc_WriteReg(TDC_CAL_ADDR_OFFSET, start_bin + i);
        tdc_WriteReg(TDC_CAL_DATA_OFFSET, time_ps[i]);
        tdc_WriteReg(TDC_CAL_CONTROL_OFFSET, TDC_CAL_WRITE);
    }
    return RP_OK;
}

int rp_TdcCalibrationReadLut(uint32_t start_bin, uint16_t* time_ps, uint32_t count) {
    if (count > 0 && time_ps == NULL)
        return RP_UIA;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    uint32_t taps = tdc_ReadReg(TDC_NUM_TAPS_OFFSET);
    if (start_bin > taps || count > taps - start_bin)
        return RP_EOOR;
    for (uint32_t i = 0; i < count; ++i) {
        tdc_WriteReg(TDC_CAL_ADDR_OFFSET, start_bin + i);
        time_ps[i] = (uint16_t)tdc_ReadRegSettled(TDC_CAL_DATA_OFFSET);
    }
    return RP_OK;
}

int rp_TdcCalibrationActivate(bool enable) {
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    if (!enable)
        return tdc_UpdateControl(TDC_CTRL_USE_LUT, 0u);

    // Hardware will swap banks only after all tap entries in the inactive bank
    // have been written.  Reject partial uploads explicitly at the API layer.
    uint32_t before = tdc_ReadRegSettled(TDC_CAL_CONTROL_OFFSET);
    if ((before & TDC_CAL_INACTIVE_READY) == 0)
        return RP_EIPV;
    tdc_WriteReg(TDC_CAL_CONTROL_OFFSET, TDC_CAL_ACTIVATE);
    uint32_t after = tdc_ReadRegSettled(TDC_CAL_CONTROL_OFFSET);
    if ((after & TDC_CAL_INACTIVE_READY) != 0 ||
        ((after ^ before) & (1u << 1)) == 0)
        return RP_EUF;
    return tdc_UpdateControl(TDC_CTRL_USE_LUT, TDC_CTRL_USE_LUT);
}

int rp_TdcCalibrationGetActive(bool* enable) {
    if (enable == NULL)
        return RP_UIA;
    int result = tdc_CheckMap();
    if (result != RP_OK)
        return result;
    *enable = (tdc_ReadReg(TDC_CONTROL_OFFSET) & TDC_CTRL_USE_LUT) != 0;
    return RP_OK;
}

int rp_TdcCalibrationComputeLut(const uint32_t* histogram, uint32_t bins,
                                uint32_t clock_period_ps, uint16_t* lut_out) {
    if (histogram == NULL || lut_out == NULL)
        return RP_UIA;
    if (bins == 0 || clock_period_ps == 0)
        return RP_EOOR;

    uint64_t total = 0;
    for (uint32_t i = 0; i < bins; ++i)
        total += histogram[i];
    if (total == 0)
        return RP_EIPV;

    uint64_t cumulative_numerator = 0;
    uint32_t previous = 0;
    for (uint32_t i = 0; i < bins; ++i) {
        uint64_t center_numerator = cumulative_numerator * 2u + histogram[i];
        uint64_t denominator = total * 2u;
        uint64_t center = (center_numerator * clock_period_ps + denominator / 2u) / denominator;
        if (center > UINT16_MAX)
            return RP_EOOR;
        if (i > 0 && center < previous)
            center = previous;
        lut_out[i] = (uint16_t)center;
        previous = (uint32_t)center;
        cumulative_numerator += histogram[i];
    }
    return RP_OK;
}
