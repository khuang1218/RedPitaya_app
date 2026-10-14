/** @brief SCPI handlers for the LVDS CARRY4 TDC. */
#ifndef TDC_SCPI_H_
#define TDC_SCPI_H_

#include "scpi/types.h"

scpi_result_t RP_TdcReset(scpi_t* context);
scpi_result_t RP_TdcEnable(scpi_t* context);
scpi_result_t RP_TdcEnableQ(scpi_t* context);
scpi_result_t RP_TdcMode(scpi_t* context);
scpi_result_t RP_TdcModeQ(scpi_t* context);
scpi_result_t RP_TdcInput(scpi_t* context);
scpi_result_t RP_TdcInputQ(scpi_t* context);
scpi_result_t RP_TdcTrigger(scpi_t* context);
scpi_result_t RP_TdcStatusQ(scpi_t* context);
scpi_result_t RP_TdcTapsQ(scpi_t* context);
scpi_result_t RP_TdcInternalTest(scpi_t* context);
scpi_result_t RP_TdcInternalTestQ(scpi_t* context);
scpi_result_t RP_TdcLaunchPeriod(scpi_t* context);
scpi_result_t RP_TdcLaunchPeriodQ(scpi_t* context);
scpi_result_t RP_TdcLaunchWidth(scpi_t* context);
scpi_result_t RP_TdcLaunchWidthQ(scpi_t* context);
scpi_result_t RP_TdcTimeout(scpi_t* context);
scpi_result_t RP_TdcTimeoutQ(scpi_t* context);
scpi_result_t RP_TdcFifoCountQ(scpi_t* context);
scpi_result_t RP_TdcFifoDataQ(scpi_t* context);
scpi_result_t RP_TdcMeasureQ(scpi_t* context);
scpi_result_t RP_TdcMeasureRawQ(scpi_t* context);
scpi_result_t RP_TdcCalibrationClear(scpi_t* context);
scpi_result_t RP_TdcCalibrationStart(scpi_t* context);
scpi_result_t RP_TdcCalibrationStop(scpi_t* context);
scpi_result_t RP_TdcCalibrationStatusQ(scpi_t* context);
scpi_result_t RP_TdcCalibrationHistogramQ(scpi_t* context);
scpi_result_t RP_TdcCalibrationLutWrite(scpi_t* context);
scpi_result_t RP_TdcCalibrationLutReadQ(scpi_t* context);
scpi_result_t RP_TdcCalibrationLutActivate(scpi_t* context);
scpi_result_t RP_TdcCalibrationLutActivateQ(scpi_t* context);

scpi_result_t RP_TdcMmcmEnable(scpi_t* context);
scpi_result_t RP_TdcMmcmEnableQ(scpi_t* context);
scpi_result_t RP_TdcMmcmReset(scpi_t* context);
scpi_result_t RP_TdcMmcmStep(scpi_t* context);
scpi_result_t RP_TdcMmcmStatusQ(scpi_t* context);
scpi_result_t RP_TdcMmcmTimeoutClear(scpi_t* context);
scpi_result_t RP_TdcMmcmPhaseCountQ(scpi_t* context);
scpi_result_t RP_TdcMmcmPhaseClear(scpi_t* context);
scpi_result_t RP_TdcMmcmCoarseDelay(scpi_t* context);
scpi_result_t RP_TdcMmcmCoarseDelayQ(scpi_t* context);

#endif
