#ifndef RP_PULSEGEN_SCPI_H
#define RP_PULSEGEN_SCPI_H
#include "scpi/types.h"
scpi_result_t RP_PulseReset(scpi_t* context);
scpi_result_t RP_PulseTiming(scpi_t* context);
scpi_result_t RP_PulseTimingQ(scpi_t* context);
scpi_result_t RP_PulsePeriodQ(scpi_t* context);
scpi_result_t RP_PulsePeriod(scpi_t* context);
scpi_result_t RP_PulseWidth(scpi_t* context);
scpi_result_t RP_PulseWidthQ(scpi_t* context);
scpi_result_t RP_PulseFrequency(scpi_t* context);
scpi_result_t RP_PulseFrequencyQ(scpi_t* context);
scpi_result_t RP_PulseOutput(scpi_t* context);
scpi_result_t RP_PulseOutputQ(scpi_t* context);
scpi_result_t RP_PulseStatusQ(scpi_t* context);
scpi_result_t RP_PulsePinQ(scpi_t* context);
#endif
