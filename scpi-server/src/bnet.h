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

#endif
