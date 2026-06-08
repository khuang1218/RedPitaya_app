/**
 * @brief SCPI handlers for the custom BNET register block.
 */
#ifndef BNET_SCPI_H_
#define BNET_SCPI_H_

#include "scpi/types.h"

scpi_result_t RP_BNetReset(scpi_t* context);
scpi_result_t RP_BNetStart(scpi_t* context);
scpi_result_t RP_BNetStatusQ(scpi_t* context);
scpi_result_t RP_BNetChannelData(scpi_t* context);
scpi_result_t RP_BNetChannelDataQ(scpi_t* context);
scpi_result_t RP_BNetOutputDataQ(scpi_t* context);
scpi_result_t RP_BNetLed6Heartbeat(scpi_t* context);
scpi_result_t RP_BNetLed6HeartbeatQ(scpi_t* context);
scpi_result_t RP_BNetCommitAll(scpi_t* context);
scpi_result_t RP_BNetMode(scpi_t* context);
scpi_result_t RP_BNetModeQ(scpi_t* context);
scpi_result_t RP_BNetVectorLength(scpi_t* context);
scpi_result_t RP_BNetVectorLengthQ(scpi_t* context);
scpi_result_t RP_BNetStreamCountQ(scpi_t* context);
scpi_result_t RP_BNetActiveMaskQ(scpi_t* context);
scpi_result_t RP_BNetPendingMaskQ(scpi_t* context);
scpi_result_t RP_BNetErrorMaskQ(scpi_t* context);
scpi_result_t RP_BNetStreamBase(scpi_t* context);
scpi_result_t RP_BNetStreamBaseQ(scpi_t* context);
scpi_result_t RP_BNetStreamLength(scpi_t* context);
scpi_result_t RP_BNetStreamLengthQ(scpi_t* context);
scpi_result_t RP_BNetStreamStride(scpi_t* context);
scpi_result_t RP_BNetStreamStrideQ(scpi_t* context);
scpi_result_t RP_BNetStreamFormat(scpi_t* context);
scpi_result_t RP_BNetStreamFormatQ(scpi_t* context);
scpi_result_t RP_BNetStreamEnable(scpi_t* context);
scpi_result_t RP_BNetStreamEnableQ(scpi_t* context);
scpi_result_t RP_BNetStreamCommit(scpi_t* context);
scpi_result_t RP_BNetStreamSwap(scpi_t* context);
scpi_result_t RP_BNetStreamClear(scpi_t* context);
scpi_result_t RP_BNetStreamStatusQ(scpi_t* context);
scpi_result_t RP_BNetStreamReadPtrQ(scpi_t* context);
scpi_result_t RP_BNetStreamDebugQ(scpi_t* context);
scpi_result_t RP_BNetDdrStartQ(scpi_t* context);
scpi_result_t RP_BNetDdrSizeQ(scpi_t* context);
scpi_result_t RP_BNetDdrSlotReserve(scpi_t* context);
scpi_result_t RP_BNetDdrSlotRelease(scpi_t* context);
scpi_result_t RP_BNetDdrSlotBaseQ(scpi_t* context);
scpi_result_t RP_BNetDdrSlotSizeQ(scpi_t* context);
scpi_result_t RP_BNetDdrSlotAttach(scpi_t* context);
scpi_result_t RP_BNetDdrSlotData(scpi_t* context);

#endif
