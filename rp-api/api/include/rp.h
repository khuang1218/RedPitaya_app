/**
 * $Id: $
 *
 * @file rp.h
 * @brief Red Pitaya library API interface
 *
 * @Author Red Pitaya
 *
 * (c) Red Pitaya  http://www.redpitaya.com
 */

#ifndef __RP_H
#define __RP_H

#include <stdbool.h>
#include <stdint.h>
#include "common/rp_log.h"
#include "rp_acq.h"
#include "rp_acq_axi.h"
#include "rp_asg_axi.h"
#include "rp_enums.h"
#include "rp_gen.h"

#define ADC_BUFFER_SIZE (16 * 1024)
#define DAC_BUFFER_SIZE (16 * 1024)

#define RISE_FALL_MIN_RATIO 0.0001  // ratio of rise/fall time to period
#define RISE_FALL_MAX_RATIO 0.1

/** @name Error codes
 *  Various error codes returned by the API.
 */
///@{

/** Success */
#define RP_OK 0
/** Failed to Open EEPROM Device */
#define RP_EOED 1
/** Failed to Open Memory Device */
#define RP_EOMD 2
/** Failed to Close Memory Device*/
#define RP_ECMD 3
/** Failed to Map Memory Device */
#define RP_EMMD 4
/** Failed to Unmap Memory Device */
#define RP_EUMD 5
/** Value Out Of Range */
#define RP_EOOR 6
/** LED Input Direction is not valid */
#define RP_ELID 7
/** Modifying Read Only field */
#define RP_EMRO 8
/** Writing to Input Pin is not valid */
#define RP_EWIP 9
/** Invalid Pin number */
#define RP_EPN 10
/** Uninitialized Input Argument */
#define RP_UIA 11
/** Failed to Find Calibration Parameters */
#define RP_FCA 12
/** Failed to Read Calibration Parameters */
#define RP_RCA 13
/** Buffer too small */
#define RP_BTS 14
/** Invalid parameter value */
#define RP_EIPV 15
/** Unsupported Feature */
#define RP_EUF 16
/** Data not normalized */
#define RP_ENN 17
/** Failed to open bus */
#define RP_EFOB 18
/** Failed to close bus */
#define RP_EFCB 19
/** Failed to acquire bus access */
#define RP_EABA 20
/** Failed to read from the bus */
#define RP_EFRB 21
/** Failed to write to the bus */
#define RP_EFWB 22
/** Extension module not connected */
#define RP_EMNC 23
/** Command not supported */
#define RP_NOTS 24
/** Error allocate memory */
#define RP_EAM 26
/** Api not initialized */
#define RP_EANI 27
/** Execution error */
#define RP_EOP 28

#define SPECTR_OUT_SIG_LEN (2 * 1024)

///@}

/** @name General
 */
///@{

/**
 * Initializes addresses for accessing registers. Does not initialize calibration parameters.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */

int rp_InitAdresses();

/**
 * Initializes the library. It must be called first, before any other library method.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */

int rp_Init();

/**
 * Initializes the library. It must be called first, before any other library method.
 * @param reset Reset to default configuration on api
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */

int rp_InitReset(bool reset);

int rp_IsApiInit();

/**
 * Releases the library resources. It must be called last, after library is not used anymore. Typically before
 * application exits.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_Release();

/**
* Resets all modules. Typically calles after rp_Init()
* application exits.
* @return If the function is successful, the return value is RP_OK.
* If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
*/
int rp_Reset();

/**
 * Retrieves the library version number
 * @return Library version
 */
const char* rp_GetVersion();

/**
 * Returns textual representation of error code.
 * @param errorCode Error code returned from API.
 * @return Textual representation of error given error code.
 */
const char* rp_GetError(int errorCode);

/**
 * Prints a set of registers for Housekeeping.
* @return If the function is successful, the return value is RP_OK.
* If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_PrintHouseRegset();

/**
 * Prints a set of registers for Oscilloscope.
* @return If the function is successful, the return value is RP_OK.
* If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_PrintOscRegset();

/**
 * Prints a set of registers for Arbitrary Signal Generator.
* @return If the function is successful, the return value is RP_OK.
* If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_PrintAsgRegset();

/**
 * Prints a set of registers for Analog Mixed Signals (AMS).
* @return If the function is successful, the return value is RP_OK.
* If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_PrintAmsRegset();

/**
 * Prints a set of registers for Daisy Chain.
* @return If the function is successful, the return value is RP_OK.
* If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_PrintDaisyRegset();

///@}
/** @name Digital loop
*/
///@{

/**
* Enable or disables digital loop. This internally connect output to input
* @param enable True if you want to enable this feature or false if you want to disable it
* @return If the function is successful, the return value is RP_OK.
*/
int rp_EnableDigitalLoop(bool enable);

///@}

/** @name Identification
 */
///@{

/**
* Gets FPGA Synthesized ID
*/
int rp_IdGetID(uint32_t* id);

/**
* Gets FPGA Unique DNA
*/
int rp_IdGetDNA(uint64_t* dna);

///@}

/**
 * LED methods
 */

int rp_LEDSetState(uint32_t state);
int rp_LEDGetState(uint32_t* state);

/**
 * Clock frequency meter
 */

int rp_GetFreqCounter(uint32_t* value);

/**
 * GPIO methods
 */

int rp_GPIOnSetDirection(uint32_t direction);
int rp_GPIOnGetDirection(uint32_t* direction);
int rp_GPIOnSetState(uint32_t state);
int rp_GPIOnGetState(uint32_t* state);
int rp_GPIOpSetDirection(uint32_t direction);
int rp_GPIOpGetDirection(uint32_t* direction);
int rp_GPIOpSetState(uint32_t state);
int rp_GPIOpGetState(uint32_t* state);

int rp_EnableDebugReg();

/** @name CAN control
 */
///@{

/**
* Enables or disables the output of the CAN controller on pins CAN0_tx: GPIO_P 7 and CAN0_rx: GPIO_N 7
* @param enable True if you want to enable this feature or false if you want to disable it
* @return If the function is successful, the return value is RP_OK.
*/
int rp_SetCANModeEnable(bool enable);

/**
* Returns the current state of GPIO outputs
* @param state True if this mode is enabled
* @return If the function is successful, the return value is RP_OK.
*/
int rp_GetCANModeEnable(bool* state);
///@}

/** @name Digital Input/Output
 */
///@{

/**
* Sets digital pins to default values. Pins DIO1_P - DIO7_P, RP_DIO0_N - RP_DIO7_N are set all INPUT and to LOW. LEDs are set to LOW/OFF
*/
int rp_DpinReset();

/**
 * Sets digital input output pin state.
 * @param pin    Digital input output pin.
 * @param state  High/Low state that will be set at the given pin.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_DpinSetState(rp_dpin_t pin, rp_pinState_t state);

/**
 * Gets digital input output pin state.
 * @param pin    Digital input output pin.
 * @param state  High/Low state that is set at the given pin.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_DpinGetState(rp_dpin_t pin, rp_pinState_t* state);

/**
 * Sets digital input output pin direction. LED pins are already automatically set to the output direction,
 * and they cannot be set to the input direction. DIOx_P and DIOx_N are must set either output or input direction
 * before they can be used. When set to input direction, it is not allowed to write into these pins.
 * @param pin        Digital input output pin.
 * @param direction  In/Out direction that will be set at the given pin.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_DpinSetDirection(rp_dpin_t pin, rp_pinDirection_t direction);

/**
 * Gets digital input output pin direction.
 * @param pin        Digital input output pin.
 * @param direction  In/Out direction that is set at the given pin.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_DpinGetDirection(rp_dpin_t pin, rp_pinDirection_t* direction);

///@}

/** @name Daisy chain clocks and triggers
 */
///@{

/**
 * Enables trigger sync over SATA daisy chain connectors.
 * Once the primary board will be triggered, the trigger will be forwarded to the secondary board over
 * the SATA connector where the trigger can be detected using rp_GenTriggerSource with EXT_NE selector.
 * Noticed that the trigger that is received over SATA is ORed with the external trigger from GPIO.
 *
 * @param enable  Turns on the mode.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_SetEnableDaisyChainTrigSync(bool enable);

/**
 * Returns the current state of the SATA daisy chain mode.
 * @param status  Current state.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_GetEnableDaisyChainTrigSync(bool* status);

/**
 * Function turns GPION_0 into trigger output for selected source - acquisition or generation
 *
 * @param enable  Turns on the mode.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_SetDpinEnableTrigOutput(bool enable);

/**
 * Returns the current mode state for GPION_0. If true, then the pin mode works as a source
 * @param status  Current state.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_GetDpinEnableTrigOutput(bool* state);

/**
 * Sets the trigger source mode. ADC/DAC
 *
 * @param mode  Sets the mode.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_SetSourceTrigOutput(rp_outTiggerMode_t mode);

/**
 * Returns the trigger source mode. ADC/DAC
 * @param mode  Returns the current mode.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_GetSourceTrigOutput(rp_outTiggerMode_t* mode);

/**
 * Enables clock sync over SATA daisy chain connectors. Primary board will start generating clock for secondary unit and so on.
 *
 * @param enable  Turns on the mode.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_SetEnableDiasyChainClockSync(bool enable);

/*
 * Returns the current state of the SATA daisy chain mode.
 * @param status  Current state.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_GetEnableDiasyChainClockSync(bool* state);

///@}

/** @name Analog Inputs/Outputs
 */
///@{

/**
* Sets analog outputs to default values (0V).
*/
int rp_ApinReset();

/**
 * Gets value from analog pin in volts.
 * @param pin    Analog pin.
 * @param value  Value on analog pin in volts
 * @param raw    raw value
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_ApinGetValue(rp_apin_t pin, float* value, uint32_t* raw);

/**
 * Gets raw value from analog pin.
 * @param pin    Analog pin.
 * @param value  Raw value on analog pin
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_ApinGetValueRaw(rp_apin_t pin, uint32_t* value);

/**
 * Sets value in volts on analog output pin.
 * @param pin    Analog output pin.
 * @param value  Value in volts to be set on given output pin.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_ApinSetValue(rp_apin_t pin, float value);

/**
 * Sets raw value on analog output pin.
 * @param pin    Analog output pin.
 * @param value  Raw value to be set on given output pin.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_ApinSetValueRaw(rp_apin_t pin, uint32_t value);

/**
 * Gets range in volts on specific pin.
 * @param pin      Analog input output pin.
 * @param min_val  Minimum value in volts on given pin.
 * @param max_val  Maximum value in volts on given pin.
 * @return If the function is successful, the return value is RP_OK.
 * If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
 */
int rp_ApinGetRange(rp_apin_t pin, float* min_val, float* max_val);

/** @name Analog Inputs
 */
///@{

/**
 * Gets value from analog pin in volts.
 * @param pin    pin index
 * @param value  voltage
 * @param raw    raw value
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_AIpinGetValue(int unsigned pin, float* value, uint32_t* raw);

/**
 * Gets raw value from analog pin.
 * @param pin    pin index
 * @param value  raw 12 bit XADC value
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_AIpinGetValueRaw(int unsigned pin, uint32_t* value);

/** @name Analog Outputs
 */
///@{

/**
* Sets analog outputs to default values (0V).
*/
int rp_AOpinReset();

/**
 * Gets value from analog pin in volts.
 * @param pin    Analog output pin index.
 * @param value  Value on analog pin in volts
 * @param raw  Value on analog pin in raw
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_AOpinGetValue(int unsigned pin, float* value, uint32_t* raw);

/**
 * Gets raw value from analog pin.
 * @param pin    Analog output pin index.
 * @param value  Raw value on analog pin
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_AOpinGetValueRaw(int unsigned pin, uint32_t* value);

/**
 * Sets value in volts on analog output pin.
 * @param pin    Analog output pin index.
 * @param value  Value in volts to be set on given output pin.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_AOpinSetValue(int unsigned pin, float value);

/**
 * Sets raw value on analog output pin.
 * @param pin    Analog output pin index.
 * @param value  Raw value to be set on given output pin.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_AOpinSetValueRaw(int unsigned pin, uint32_t value);

/**
 * Gets range in volts on specific pin.
 * @param pin      Analog input output pin index.
 * @param min_val  Minimum value in volts on given pin.
 * @param max_val  Maximum value in volts on given pin.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_AOpinGetRange(int unsigned pin, float* min_val, float* max_val);

///@}

/** @name PLL Control for 250-12
*/
///@{

/**
* Only works with Redpitaya 250-12 otherwise returns RP_NOTS
* @param enable return current state.
* @return If the function is successful, the return value is RP_OK.
* If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
*/
int rp_GetPllControlEnable(bool* enable);

/**
* Only works with Redpitaya 250-12 otherwise returns RP_NOTS
* @param enable Flag enabling PLL control.
* @return If the function is successful, the return value is RP_OK.
* If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
*/
int rp_SetPllControlEnable(bool enable);

/**
* Only works with Redpitaya 250-12 otherwise returns RP_NOTS
* @param status Get current state.
* @return If the function is successful, the return value is RP_OK.
* If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
*/
int rp_GetPllControlLocked(bool* status);
///@}

/** @name PLL Control for 250-12
*/
///@{

/**
* Only works with Redpitaya 250-12 otherwise returns RP_NOTS
* @param value Trigger level. Positive value.
* @return If the function is successful, the return value is RP_OK.
* If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
*/
int rp_SetExternalTriggerLevel(float value);

/**
* Only works with Redpitaya 250-12 otherwise returns RP_NOTS
* @param value Returns the trigger level.
* @return If the function is successful, the return value is RP_OK.
* If the function is unsuccessful, the return value is any of RP_E* values that indicate an error.
*/
int rp_GetExternalTriggerLevel(float* value);

///@}

/** @name LVDS carry-chain time-to-digital converter
 */
///@{

typedef enum {
    RP_TDC_MODE_SINGLE = 0,
    RP_TDC_MODE_CONTINUOUS = 1,
    RP_TDC_MODE_CALIBRATION = 2
} rp_tdc_mode_t;

/** Per-result status flags returned in rp_tdc_result_t::status. */
#define RP_TDC_RESULT_VALID                (1u << 0)
#define RP_TDC_RESULT_NO_TRANSITION        (1u << 1)
#define RP_TDC_RESULT_MULTIPLE_TRANSITIONS (1u << 2)
#define RP_TDC_RESULT_ALL_ZERO             (1u << 3)
#define RP_TDC_RESULT_ALL_ONE              (1u << 4)
#define RP_TDC_RESULT_BUBBLE_CORRECTED     (1u << 5)
#define RP_TDC_RESULT_TIMEOUT              (1u << 6)
#define RP_TDC_RESULT_FIFO_OVERFLOW        (1u << 7)

/** Live TDC_STATUS register flags returned by rp_TdcGetStatus(). */
#define RP_TDC_STATUS_BUSY                 (1u << 0)
#define RP_TDC_STATUS_FIFO_NONEMPTY        (1u << 1)
#define RP_TDC_STATUS_FIFO_FULL            (1u << 2)
#define RP_TDC_STATUS_LAST_TIMEOUT         (1u << 3)
#define RP_TDC_STATUS_LAST_INVALID         (1u << 4)
#define RP_TDC_STATUS_ACTIVE_LUT_BANK      (1u << 5)
#define RP_TDC_STATUS_HIST_CLEAR_BUSY      (1u << 6)
#define RP_TDC_STATUS_FIFO_OVERFLOW        (1u << 7)
#define RP_TDC_STATUS_FIFO_LEVEL_SHIFT     8u
#define RP_TDC_STATUS_FIFO_LEVEL_MASK      (0x1ffu << RP_TDC_STATUS_FIFO_LEVEL_SHIFT)
#define RP_TDC_STATUS_CALIBRATION_COMPLETE (1u << 17)
#define RP_TDC_STATUS_INTERNAL_TEST         (1u << 18)
#define RP_TDC_STATUS_MMCM_SWEEP_ENABLE     (1u << 19)
#define RP_TDC_STATUS_MMCM_LOCKED           (1u << 20)
#define RP_TDC_STATUS_MMCM_PS_BUSY          (1u << 21)

/** Dedicated MMCM phase-sweep MMCM_STATUS register flags, see
 *  rp_TdcMmcmGetStatus(). */
#define RP_TDC_MMCM_STATUS_LOCKED     (1u << 0)
#define RP_TDC_MMCM_STATUS_PS_BUSY    (1u << 1)
#define RP_TDC_MMCM_STATUS_PS_TIMEOUT (1u << 2)

typedef struct {
    uint32_t sequence_id;
    uint32_t status;
    uint32_t coarse_cycles;
    uint32_t fine_raw_index;
    uint32_t fine_time_ps;
    uint64_t total_time_ps;
    uint32_t analogue_code;
} rp_tdc_result_t;

int rp_TdcReset(void);
int rp_TdcEnable(bool enable);
int rp_TdcGetEnable(bool* enable);
int rp_TdcSetMode(rp_tdc_mode_t mode);
int rp_TdcGetMode(rp_tdc_mode_t* mode);
int rp_TdcSetLaunchPeriod(uint32_t cycles);
int rp_TdcGetLaunchPeriod(uint32_t* cycles);
int rp_TdcSetLaunchWidth(uint32_t cycles);
int rp_TdcGetLaunchWidth(uint32_t* cycles);
int rp_TdcSetTimeout(uint32_t cycles);
int rp_TdcGetTimeout(uint32_t* cycles);
int rp_TdcTrigger(void);
int rp_TdcGetStatus(uint32_t* status);
int rp_TdcGetFifoLevel(uint32_t* level);
int rp_TdcReadResult(rp_tdc_result_t* result);
int rp_TdcGetLastResult(rp_tdc_result_t* result);
int rp_TdcGetNumTaps(uint32_t* taps);
int rp_TdcGetRawCapture(uint32_t start_word, uint32_t* words, uint32_t count);
int rp_TdcSetInternalTest(bool enable);
int rp_TdcGetInternalTest(bool* enable);

/** @name Dedicated MMCM phase-sweep self-test
 *
 * A dedicated MMCME2_ADV, belonging only to the TDC self-test and never the
 * shared red_pitaya_pll, regenerates the TDC sampling clock frequency at a
 * software-commanded, dynamically stepped phase and releases exactly one
 * measurement edge per rp_TdcMmcmPhaseStep()/trigger cycle. It produces a
 * commanded nominal coarse+fine phase for boundary, monotonicity and
 * repeatability testing; it does not calibrate absolute picoseconds and does
 * not exercise the E3 electrical path. See doc/tdc_registers.md.
 */
///@{
int rp_TdcMmcmSetSweepEnable(bool enable);
int rp_TdcMmcmGetSweepEnable(bool* enable);
int rp_TdcMmcmReset(void);
/** Request one dynamic phase-shift step and wait for it to complete.
 *  Returns RP_EIPV if the MMCM is not locked, RP_EUF if the request was not
 *  acknowledged within the FPGA watchdog. */
int rp_TdcMmcmPhaseStep(bool increase);
int rp_TdcMmcmGetPhaseCount(int32_t* count);
int rp_TdcMmcmClearPhaseCount(void);
int rp_TdcMmcmSetCoarseDelay(uint16_t cycles);
int rp_TdcMmcmGetCoarseDelay(uint16_t* cycles);
int rp_TdcMmcmGetStatus(uint32_t* status);
int rp_TdcMmcmClearTimeout(void);
///@}

int rp_TdcCalibrationClearHistogram(void);
int rp_TdcCalibrationStart(uint32_t target_events);
int rp_TdcCalibrationStop(void);
int rp_TdcCalibrationGetStatus(uint32_t* status, uint32_t* events_collected);
int rp_TdcCalibrationReadHistogram(uint32_t start_bin, uint32_t* counts, uint32_t count);
int rp_TdcCalibrationWriteLut(uint32_t start_bin, const uint16_t* time_ps, uint32_t count);
int rp_TdcCalibrationReadLut(uint32_t start_bin, uint16_t* time_ps, uint32_t count);
int rp_TdcCalibrationActivate(bool enable);
int rp_TdcCalibrationGetActive(bool* enable);
int rp_TdcCalibrationComputeLut(const uint32_t* histogram, uint32_t bins,
                                uint32_t clock_period_ps, uint16_t* lut_out);

///@}

/** @name Custom Butterfly Network Register Block
 */
///@{

/**
 * Writes one scalar BNET logical channel register.
 * @param channel Channel index, 0..7.
 * @param value   Signed 32-bit value to write.
 * @return        RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetChannelData(uint32_t channel, int32_t value);

/**
 * Reads one scalar BNET logical channel register.
 * @param channel Channel index, 0..7.
 * @param value   Returned signed 32-bit value.
 * @return        RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetChannelData(uint32_t channel, int32_t* value);

/**
 * Starts the scalar BNET test computation.
 * @return RP_OK - successful, RP_E* - failure
 */
int rp_BNetStart();

/**
 * Commits the inactive buffer for every enabled BNET stream.
 * @return RP_OK - successful, RP_E* - failure
 */
int rp_BNetCommitAllEnabledStreams();

/**
 * Soft-resets the BNET register block.
 * @return RP_OK - successful, RP_E* - failure
 */
int rp_BNetReset();

/**
 * Reads the BNET status register.
 * @param status Returned status bits.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetStatus(uint32_t* status);

/**
 * Sets BNET input mode. 0=ASG test, 1=ADC real-time, 2=DDR streams.
 * @param mode Input mode value.
 * @return     RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetInputMode(uint32_t mode);

/**
 * Gets BNET input mode.
 * @param mode Returned input mode value.
 * @return     RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetInputMode(uint32_t* mode);

/**
 * Writes the full BNET configuration register.
 * CONFIG[1:0] selects input mode, CONFIG[2] enables auto ping/pong swap on done,
 * CONFIG[3] enables auto-restart after auto-swap, CONFIG[4] enables static
 * weight reuse in the serial engine, and CONFIG[5] enables the static-weight
 * frame pipeline in DDR mode. CONFIG[6] serializes both BNET output lanes onto
 * DAC output 1 and drives DAC output 2 to zero. CONFIG[7] splits every raw
 * 14-bit BNET result into bits[13:7] and bits[6:0] using centered offset-binary
 * DAC transport. CONFIG[8] combines neighboring IN1 fields into one 14-bit
 * scope acquisition word. CONFIG[9] selects the neighboring-sample pair phase.
 * These settings do not alter the BNET compute input.
 * @param config Raw configuration bits.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetConfig(uint32_t config);

/**
 * Reads the full BNET configuration register.
 * @param config Returned raw configuration bits.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetConfig(uint32_t* config);

/**
 * Enables or disables static weight reuse in the serial BNET engine.
 * When enabled, weights already loaded into FPGA RAM are reused on the next run.
 * @param enable true to reuse preloaded weights, false to stream weights again.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetStaticWeightReuse(bool enable);

/**
 * Reads the static weight reuse enable bit.
 * @param enable Returned static weight reuse state.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetStaticWeightReuse(bool* enable);

/**
 * Enables or disables the static-weight frame pipeline.
 * This selects the fixed-weight pipeline path when BNET input mode is DDR.
 * @param enable true to use the static pipeline, false to use the serial engine.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetStaticPipeline(bool enable);

/**
 * Reads the static-weight frame pipeline enable bit.
 * @param enable Returned static pipeline state.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetStaticPipeline(bool* enable);

/**
 * Enables or disables single-DAC BNET output serialization.
 * When enabled, y0/y1 are emitted sequentially on DAC output 1 and DAC output 2
 * is held at zero.
 * @param enable true to serialize onto one DAC, false to use both DAC outputs.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetSingleDacOutput(bool enable);

/**
 * Reads the single-DAC BNET output enable bit.
 * @param enable Returned single-DAC output state.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetSingleDacOutput(bool* enable);

/**
 * Enables or disables raw 14-to-7-bit BNET DAC output splitting.
 * When enabled, each 14-bit result is emitted on DAC output 1 as two samples:
 * bits[13:7] then bits[6:0]. Each unsigned field uses centered offset-binary
 * DAC transport so values 0..127 map monotonically across the signed range.
 * @param enable true to split each result, false to emit normal 14-bit results.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetSplitDacOutput(bool enable);

/**
 * Reads the raw 14-to-7-bit BNET DAC output splitting state.
 * @param enable Returned split-output state.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetSplitDacOutput(bool* enable);

/**
 * Enables or disables bit-combined IN1 scope acquisition.
 * The first ADC[13:7] field becomes result[13:7] and the second ADC[13:7]
 * field becomes result[6:0]. The result is held for two ADC clocks; configure
 * acquisition decimation 2 to receive one reconstructed word per RF pair.
 * This setting does not alter the BNET compute input, and IN2 remains raw.
 * @param enable true for combined IN1 acquisition, false for normal acquisition.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetCombineAdcInput(bool enable);

/**
 * Reads the bit-combined IN1 acquisition state.
 * @param enable Returned ADC-combine state.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetCombineAdcInput(bool* enable);

/**
 * Selects which neighboring IN1 sample starts a reconstructed 14-bit word.
 * Phase 0 combines samples (0,1), (2,3), ...; phase 1 combines samples
 * (1,2), (3,4), ... after each BNET start/reset. Use this to compensate an
 * odd number of DAC, cable, and ADC pipeline clocks.
 * @param phase false for phase 0, true for phase 1.
 * @return      RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetCombineAdcPhase(bool phase);

/**
 * Reads the neighboring-sample phase used by the IN1 bit combiner.
 * @param phase Returned phase selection.
 * @return      RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetCombineAdcPhase(bool* phase);

/**
 * Sets the runtime static-SDF vector length.
 * @param samples Supported values are 1024, 2048, and 4096.
 * @return        RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetVectorLength(uint32_t samples);

/**
 * Gets the BNET vector length register.
 * @param samples Returned vector length in samples.
 * @return        RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetVectorLength(uint32_t* samples);

/**
 * Selects the static-weight bank for the next 1024- or 2048-point run.
 * A selection arms one run and must be repeated before every subsequent run.
 * Bank selection is unsupported for 4096-point mode, which always uses bank 0.
 * @param bank 0..3 for 1024 points or 0..1 for 2048 points.
 * @return RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetWeightBank(uint32_t bank);

/** Reads the currently selected static-weight bank number. */
int rp_BNetGetWeightBank(uint32_t* bank);

/** Returns the number of resident banks for the selected vector length. */
int rp_BNetGetWeightBankCount(uint32_t* count);

/**
 * Gets the number of logical BNET DDR streams exposed by hardware.
 * @param count Returned stream count.
 * @return      RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetStreamCount(uint32_t* count);

/**
 * Gets the stream active-buffer mask.
 * @param mask Returned active mask.
 * @return     RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetActiveMask(uint32_t* mask);

/**
 * Gets the stream pending-swap mask.
 * @param mask Returned pending mask.
 * @return     RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetPendingMask(uint32_t* mask);

/**
 * Gets the stream error mask.
 * @param mask Returned error mask.
 * @return     RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetErrorMask(uint32_t* mask);

/**
 * Reads one scalar BNET output register.
 * @param index Output index, 0..3.
 * @param value Returned signed 32-bit value.
 * @return      RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetOutputData(uint32_t index, int32_t* value);

/**
 * Reads one BNET hardware timing counter from the last run.
 * Index 0=total start-to-done, 1=load/weight-load, 2=compute/input-load,
 * 3=playback/output, 4=input-load, 5=latency.
 * Values are adc_clk cycles.
 * @param index  Timing counter index.
 * @param cycles Returned cycle count.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetTiming(uint32_t index, uint32_t* cycles);

/**
 * Gets the number of digital BNET output samples captured from the last run.
 * @param count Returned captured sample count.
 * @return      RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetCaptureCount(uint32_t* count);

/**
 * Gets the digital BNET output capture status register.
 * Bit 0 indicates capture overflow/truncation.
 * @param status Returned capture status flags.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetCaptureStatus(uint32_t* status);

/**
 * Reads one digital BNET output capture sample.
 * @param index Captured sample index.
 * @param value Returned signed 32-bit sample value.
 * @return      RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetCaptureData(uint32_t index, int32_t* value);

/**
 * Reads a contiguous block of digital BNET output capture samples.
 * @param start   First captured sample index.
 * @param samples Number of samples to read.
 * @param values  Returned signed 16-bit sample buffer.
 * @return        RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetCaptureDataBlock(uint32_t start, uint32_t samples, int16_t* values);

/**
 * Sets one BNET stream ping/pong base address.
 * @param stream  Stream index.
 * @param buffer  Buffer index, 0=BASE0/ping, 1=BASE1/pong.
 * @param address DDR physical base address.
 * @return        RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetStreamBase(uint32_t stream, uint32_t buffer, uint32_t address);

/**
 * Gets one BNET stream ping/pong base address.
 * @param stream  Stream index.
 * @param buffer  Buffer index, 0=BASE0/ping, 1=BASE1/pong.
 * @param address Returned DDR physical base address.
 * @return        RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetStreamBase(uint32_t stream, uint32_t buffer, uint32_t* address);

/**
 * Sets one BNET stream buffer length.
 * @param stream Stream index.
 * @param bytes  Buffer length in bytes.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetStreamLength(uint32_t stream, uint32_t bytes);

/**
 * Gets one BNET stream buffer length.
 * @param stream Stream index.
 * @param bytes  Returned buffer length in bytes.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetStreamLength(uint32_t stream, uint32_t* bytes);

/**
 * Sets one BNET stream byte stride.
 * @param stream Stream index.
 * @param bytes  Byte stride.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetStreamStride(uint32_t stream, uint32_t bytes);

/**
 * Gets one BNET stream byte stride.
 * @param stream Stream index.
 * @param bytes  Returned byte stride.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetStreamStride(uint32_t stream, uint32_t* bytes);

/**
 * Sets one BNET stream format tag.
 * @param stream Stream index.
 * @param format Format tag value.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetStreamFormat(uint32_t stream, uint32_t format);

/**
 * Gets one BNET stream format tag.
 * @param stream Stream index.
 * @param format Returned format tag value.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetStreamFormat(uint32_t stream, uint32_t* format);

/**
 * Enables or disables one BNET stream.
 * @param stream Stream index.
 * @param enable true to enable the stream.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetEnableStream(uint32_t stream, bool enable);

/**
 * Gets one BNET stream enable state.
 * @param stream Stream index.
 * @param enable Returned enable state.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetStreamEnable(uint32_t stream, bool* enable);

/**
 * Commits one BNET stream buffer as pending.
 * @param stream Stream index.
 * @param buffer Buffer index, 0=BASE0/ping, 1=BASE1/pong.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetCommitStreamBuffer(uint32_t stream, uint32_t buffer);

/**
 * Forces one BNET stream to swap active buffers immediately.
 * @param stream Stream index.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetForceStreamSwap(uint32_t stream);

/**
 * Clears descriptor error bits for one BNET stream.
 * @param stream Stream index.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetClearStreamError(uint32_t stream);

/**
 * Gets one BNET stream status register.
 * @param stream Stream index.
 * @param status Returned stream status bits.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetStreamStatus(uint32_t stream, uint32_t* status);

/**
 * Gets one BNET stream read pointer.
 * @param stream   Stream index.
 * @param read_ptr Returned read pointer.
 * @return         RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetStreamReadPtr(uint32_t stream, uint32_t* read_ptr);

/**
 * Gets one BNET stream debug register.
 * @param stream Stream index.
 * @param index  Debug register index, 0 or 1.
 * @param value  Returned debug register value.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetStreamDebug(uint32_t stream, uint32_t index, uint32_t* value);

/**
 * Gets the OS-reserved DDR region available for AXI buffers.
 * @param start Returned DDR physical start address.
 * @param size  Returned region size in bytes.
 * @return      RP_OK - successful, RP_E* - failure
 */
int rp_BNetDdrGetMemoryRegion(uint32_t* start, uint32_t* size);

/**
 * Reserves one BNET DDR upload slot and maps it through /dev/mem.
 * @param slot    Software slot index, 0..7.
 * @param address DDR physical base address.
 * @param size    Slot size in bytes, must be a multiple of 0x80.
 * @return        RP_OK - successful, RP_E* - failure
 */
int rp_BNetDdrReserve(uint32_t slot, uint32_t address, uint32_t size);

/**
 * Releases one BNET DDR upload slot.
 * @param slot Software slot index, 0..7.
 * @return     RP_OK - successful, RP_E* - failure
 */
int rp_BNetDdrRelease(uint32_t slot);

/**
 * Gets one reserved BNET DDR slot base address.
 * @param slot    Software slot index, 0..7.
 * @param address Returned DDR physical base address.
 * @return        RP_OK - successful, RP_E* - failure
 */
int rp_BNetDdrGetSlotBase(uint32_t slot, uint32_t* address);

/**
 * Gets one reserved BNET DDR slot size.
 * @param slot Software slot index, 0..7.
 * @param size Returned slot size in bytes.
 * @return     RP_OK - successful, RP_E* - failure
 */
int rp_BNetDdrGetSlotSize(uint32_t slot, uint32_t* size);

/**
 * Wires a reserved BNET DDR slot to a hardware stream ping/pong buffer.
 * This sets the stream base address and length from the slot.
 * @param slot   Software slot index, 0..7.
 * @param stream BNET stream index.
 * @param buffer Buffer index, 0=BASE0/ping, 1=BASE1/pong.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetDdrAttachStreamBuffer(uint32_t slot, uint32_t stream, uint32_t buffer);

/**
 * Writes raw bytes into a reserved BNET DDR slot.
 * Use this for byte-packed fixed-point data, for example little-endian int16 weights.
 * @param slot         Software slot index, 0..7.
 * @param offset_bytes Byte offset inside the slot.
 * @param data         Source byte buffer.
 * @param bytes        Number of bytes to write.
 * @return             RP_OK - successful, RP_E* - failure
 */
int rp_BNetDdrWriteRaw(uint32_t slot, uint32_t offset_bytes, const uint8_t* data, uint32_t bytes);

/**
 * Writes signed 16-bit fixed-point words into a reserved BNET DDR slot.
 * @param slot           Software slot index, 0..7.
 * @param offset_samples Sample offset inside the slot.
 * @param data           Source signed 16-bit buffer.
 * @param samples        Number of 16-bit samples to write.
 * @return               RP_OK - successful, RP_E* - failure
 */
int rp_BNetDdrWriteI16(uint32_t slot, uint32_t offset_samples, const int16_t* data, uint32_t samples);

/**
 * Writes unsigned 16-bit fixed-point words into a reserved BNET DDR slot.
 * @param slot           Software slot index, 0..7.
 * @param offset_samples Sample offset inside the slot.
 * @param data           Source unsigned 16-bit buffer.
 * @param samples        Number of 16-bit samples to write.
 * @return               RP_OK - successful, RP_E* - failure
 */
int rp_BNetDdrWriteU16(uint32_t slot, uint32_t offset_samples, const uint16_t* data, uint32_t samples);

/**
 * Enables or disables the custom LED6 heartbeat.
 * @param enable true to blink LED6, false to drive LED6 low.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetSetLed6Heartbeat(bool enable);

/**
 * Reads the custom LED6 heartbeat enable bit.
 * @param enable Returned heartbeat-enable state.
 * @return       RP_OK - successful, RP_E* - failure
 */
int rp_BNetGetLed6Heartbeat(bool* enable);

///@}

#endif  //__RP_H
