// =============================================================================
// URTC-COMMON - firmware_base/urtc_ring.h
// Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
// GPL-3.0-or-later - see LICENSE
// =============================================================================
// A single-producer / single-consumer byte ring: the only thing a receive interrupt (or a DMA half-transfer
// handler) may do with a byte. The main loop takes the bytes out and feeds them to the deframer and to the
// state machines, so those stay in ONE context and need no lock. The producer owns `head`, the consumer owns
// `tail`, and each index is published with a release store and read with an acquire load, so a byte is always
// visible before the index that announces it.
//
// The size must be a power of two (the indices wrap by masking). One slot is kept free to tell "full" from
// "empty", so a ring of `size` bytes holds `size - 1`. A byte that does not fit is dropped and counted: the
// deframer then sees a gap, which its length and CRC checks already turn into a lost frame.
//
// Header only, no library: the compiler's own atomic builtins give the ordering (a plain load/store plus a barrier
// on a Cortex-M). Copied into each firmware repository by tools/vendor_copy.py (set "firmware_ring").
#ifndef URTC_RING_H
#define URTC_RING_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint8_t *storage;
    uint16_t mask;                // size - 1
    volatile uint16_t head;       // next index to write; written only by the producer
    volatile uint16_t tail;       // next index to read; written only by the consumer
    volatile uint16_t dropped;    // running count of bytes that did not fit (wraps); written only by the producer
    uint16_t dropped_seen;        // the value of `dropped` the consumer already reported; written only by the consumer
} urtc_ring_t;

#define URTC_RING_LOAD_ACQUIRE(p)       __atomic_load_n((p), __ATOMIC_ACQUIRE)
#define URTC_RING_STORE_RELEASE(p, v)   __atomic_store_n((p), (v), __ATOMIC_RELEASE)

// `size` must be a power of two between 2 and 32768. Returns false (and leaves the ring unusable) otherwise.
static inline bool urtc_ring_init(urtc_ring_t *ring, uint8_t *storage, uint16_t size)
{
    if (ring == NULL) {
        return false;
    }
    ring->storage = NULL;
    ring->mask = 0u;
    ring->head = 0u;
    ring->tail = 0u;
    ring->dropped = 0u;
    ring->dropped_seen = 0u;
    if (storage == NULL || size < 2u || size > 32768u || (size & (uint16_t)(size - 1u)) != 0u) {
        return false;
    }
    ring->storage = storage;
    ring->mask = (uint16_t)(size - 1u);
    return true;
}

// Producer side (interrupt). Returns false when the ring is full and the byte was dropped.
static inline bool urtc_ring_put(urtc_ring_t *ring, uint8_t byte)
{
    if (ring == NULL || ring->storage == NULL) {
        return false;
    }
    const uint16_t head = ring->head;                          // only this side writes it
    const uint16_t next = (uint16_t)((head + 1u) & ring->mask);
    if (next == URTC_RING_LOAD_ACQUIRE(&ring->tail)) {
        ring->dropped = (uint16_t)(ring->dropped + 1u);
        return false;
    }
    ring->storage[head] = byte;
    URTC_RING_STORE_RELEASE(&ring->head, next);                // the byte is visible before the index
    return true;
}

// Consumer side (main loop). Returns false when there is nothing to read.
static inline bool urtc_ring_get(urtc_ring_t *ring, uint8_t *out)
{
    if (ring == NULL || ring->storage == NULL || out == NULL) {
        return false;
    }
    const uint16_t tail = ring->tail;                          // only this side writes it
    if (tail == URTC_RING_LOAD_ACQUIRE(&ring->head)) {
        return false;
    }
    *out = ring->storage[tail];
    URTC_RING_STORE_RELEASE(&ring->tail, (uint16_t)((tail + 1u) & ring->mask));
    return true;
}

// Bytes waiting to be read (a snapshot: the producer may add more at any moment).
static inline uint16_t urtc_ring_count(const urtc_ring_t *ring)
{
    if (ring == NULL || ring->storage == NULL) {
        return 0u;
    }
    const uint16_t head = URTC_RING_LOAD_ACQUIRE(&ring->head);
    const uint16_t tail = URTC_RING_LOAD_ACQUIRE(&ring->tail);
    return (uint16_t)((head - tail) & ring->mask);
}

// Bytes dropped since the last call; consumer side. (More than 65535 drops between two calls are under-counted.)
static inline uint16_t urtc_ring_take_dropped(urtc_ring_t *ring)
{
    if (ring == NULL) {
        return 0u;
    }
    const uint16_t dropped = URTC_RING_LOAD_ACQUIRE(&ring->dropped);
    const uint16_t since = (uint16_t)(dropped - ring->dropped_seen);
    ring->dropped_seen = dropped;
    return since;
}

#endif // URTC_RING_H
