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
int rp_BNetCommitAllEnabledStreams();
int rp_BNetReset();
int rp_BNetGetStatus(uint32_t* status);
int rp_BNetSetInputMode(uint32_t mode);
int rp_BNetGetInputMode(uint32_t* mode);
int rp_BNetSetConfig(uint32_t config);
int rp_BNetGetConfig(uint32_t* config);
int rp_BNetSetStaticWeightReuse(bool enable);
int rp_BNetGetStaticWeightReuse(bool* enable);
int rp_BNetSetStaticPipeline(bool enable);
int rp_BNetGetStaticPipeline(bool* enable);
int rp_BNetSetVectorLength(uint32_t samples);
int rp_BNetGetVectorLength(uint32_t* samples);
int rp_BNetGetStreamCount(uint32_t* count);
int rp_BNetGetActiveMask(uint32_t* mask);
int rp_BNetGetPendingMask(uint32_t* mask);
int rp_BNetGetErrorMask(uint32_t* mask);
int rp_BNetGetOutputData(uint32_t index, int32_t* value);
int rp_BNetGetTiming(uint32_t index, uint32_t* cycles);
int rp_BNetSetStreamBase(uint32_t stream, uint32_t buffer, uint32_t address);
int rp_BNetGetStreamBase(uint32_t stream, uint32_t buffer, uint32_t* address);
int rp_BNetSetStreamLength(uint32_t stream, uint32_t bytes);
int rp_BNetGetStreamLength(uint32_t stream, uint32_t* bytes);
int rp_BNetSetStreamStride(uint32_t stream, uint32_t bytes);
int rp_BNetGetStreamStride(uint32_t stream, uint32_t* bytes);
int rp_BNetSetStreamFormat(uint32_t stream, uint32_t format);
int rp_BNetGetStreamFormat(uint32_t stream, uint32_t* format);
int rp_BNetEnableStream(uint32_t stream, bool enable);
int rp_BNetGetStreamEnable(uint32_t stream, bool* enable);
int rp_BNetCommitStreamBuffer(uint32_t stream, uint32_t buffer);
int rp_BNetForceStreamSwap(uint32_t stream);
int rp_BNetClearStreamError(uint32_t stream);
int rp_BNetGetStreamStatus(uint32_t stream, uint32_t* status);
int rp_BNetGetStreamReadPtr(uint32_t stream, uint32_t* read_ptr);
int rp_BNetGetStreamDebug(uint32_t stream, uint32_t index, uint32_t* value);
int rp_BNetDdrGetMemoryRegion(uint32_t* start, uint32_t* size);
int rp_BNetDdrReserve(uint32_t slot, uint32_t address, uint32_t size);
int rp_BNetDdrRelease(uint32_t slot);
int rp_BNetDdrGetSlotBase(uint32_t slot, uint32_t* address);
int rp_BNetDdrGetSlotSize(uint32_t slot, uint32_t* size);
int rp_BNetDdrAttachStreamBuffer(uint32_t slot, uint32_t stream, uint32_t buffer);
int rp_BNetDdrWriteRaw(uint32_t slot, uint32_t offset_bytes, const uint8_t* data, uint32_t bytes);
int rp_BNetDdrWriteI16(uint32_t slot, uint32_t offset_samples, const int16_t* data, uint32_t samples);
int rp_BNetDdrWriteU16(uint32_t slot, uint32_t offset_samples, const uint16_t* data, uint32_t samples);
int rp_BNetSetLed6Heartbeat(bool enable);
int rp_BNetGetLed6Heartbeat(bool* enable);

#endif
