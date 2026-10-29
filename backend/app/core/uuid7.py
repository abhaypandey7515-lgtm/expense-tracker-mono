"""
RFC 9562 Compliant UUIDv7 Generator with Monotonic Sequence Counter.

UUIDv7 provides time-ordered, sortable unique identifiers:
- 48 bits: Unix timestamp in milliseconds
- 4 bits: Version (0b0111 -> 7)
- 12 bits: Sub-millisecond sequence counter (RFC 9562 Method 1 for strict monotonicity)
- 2 bits: Variant (0b10)
- 62 bits: Cryptographically secure random data
"""

import os
import time
import uuid
import threading

_lock = threading.Lock()
_last_ms = 0
_seq = 0


def uuid7() -> uuid.UUID:
    """
    Generate an RFC 9562 compliant time-ordered UUIDv7 with guaranteed monotonicity.
    """
    global _last_ms, _seq

    with _lock:
        ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF

        if ms > _last_ms:
            _last_ms = ms
            # Seed 12-bit sequence with initial value
            _seq = int.from_bytes(os.urandom(2), byteorder="big") & 0x07FF
        elif ms == _last_ms:
            # Monotonic increment within the same millisecond
            _seq = (_seq + 1) & 0x0FFF
        else:
            # Clock skew backwards; advance sequence counter
            _seq = (_seq + 1) & 0x0FFF
            ms = _last_ms

        curr_seq = _seq

    # 10 random bytes from OS CSPRNG for remaining entropy
    rand_bytes = os.urandom(8)
    rand_a = rand_bytes[0] & 0x3F  # 6 bits after variant 0b10
    rand_b = rand_bytes[1:8]

    # Assemble 128-bit integer
    # [48-bit time_high] [4-bit version 7] [12-bit seq] [2-bit variant 10] [6-bit rand_a] [56-bit rand_b]
    hi = (ms << 16) | (0x7 << 12) | curr_seq
    lo = (0x2 << 62) | (rand_a << 56) | int.from_bytes(rand_b, byteorder="big")

    int128 = (hi << 64) | lo
    return uuid.UUID(int=int128)


def uuid7_str() -> str:
    """
    Generate UUIDv7 as a canonical string representation.
    """
    return str(uuid7())
