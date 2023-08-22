import argparse
import asyncio
import sys
import time
from typing import Final, Optional, Iterable, Tuple, Union

import sounddevice as sd

_RATE: Final = 16000
_CHANNELS: Final = 1


def record(
    device: Optional[Union[str, int]],
    samples_per_chunk: int = 1280,
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
