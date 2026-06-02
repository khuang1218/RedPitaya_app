/**
 * @brief Custom butterfly-network register block interface.
 */
#ifndef __BNET_H
#define __BNET_H

#include <stdbool.h>
#include <stdint.h>

int bnet_Init();
int bnet_Release();

int rp_BNetSetChannelData(uint32_t channel, int32_t value);
int rp_BNetGetChannelData(uint32_t channel, int32_t* value);
int rp_BNetStart();
int rp_BNetReset();
int rp_BNetGetStatus(uint32_t* status);
int rp_BNetGetOutputData(uint32_t index, int32_t* value);
int rp_BNetSetLed6Heartbeat(bool enable);
int rp_BNetGetLed6Heartbeat(bool* enable);

#endif
