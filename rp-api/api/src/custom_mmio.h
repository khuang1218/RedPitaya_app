#ifndef RP_CUSTOM_MMIO_H
#define RP_CUSTOM_MMIO_H
#include <atomic>
#include <stdint.h>

// Host regressions provide a register model; production remains direct MMIO.
#ifdef RP_CUSTOM_MMIO_TEST
uint32_t custom_mmio_Read(volatile uint32_t* address);
void custom_mmio_Write(volatile uint32_t* address, uint32_t value);
#else
inline uint32_t custom_mmio_Read(volatile uint32_t* address) { return *address; }
inline void custom_mmio_Write(volatile uint32_t* address, uint32_t value) {
    *address = value;
    std::atomic_thread_fence(std::memory_order_seq_cst);
}
#endif
#endif
