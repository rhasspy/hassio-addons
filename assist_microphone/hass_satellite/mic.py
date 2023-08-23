import argparse
import asyncio
import sys
import time
from typing import Final, Iterable, Optional, Tuple, Union

import sounddevice as sd

_RATE: Final = 16000
_CHANNELS: Final = 1
_SAMPLES_PER_CHUNK = int(0.03 * _RATE)  # 30ms


def record(
    device: Optional[Union[str, int]],
    samples_per_chunk: int = _SAMPLES_PER_CHUNK,
) -> Iterable[Tuple[int, bytes]]:
    """Yield mic samples with a timestamp."""
    with sd.RawInputStream(
        device=device,
        samplerate=_RATE,
        channels=_CHANNELS,
        blocksize=samples_per_chunk,
        dtype="int16",
    ) as stream:
        while True:
            chunk, _overflowed = stream.read(samples_per_chunk)
            chunk = bytes(chunk)
            yield time.monotonic_ns(), chunk
