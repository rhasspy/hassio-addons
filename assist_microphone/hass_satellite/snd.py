import logging
import subprocess
import wave

import sounddevice as sd

_LOGGER  = logging.getLogger()

def play(
    media: str,
    stream: sd.RawOutputStream,
    sample_rate: int,
    samples_per_chunk: int = 1024,
    volume: float = 1.0,
) -> None:
    cmd = [
        "ffmpeg",
        "-i",
        media,
        "-f",
        "wav",
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        "-filter:a",
        f"volume={volume}",
        "-",
    ]
    _LOGGER.debug("play: %s", cmd)

    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as proc:
        with wave.open(proc.stdout, "rb") as wav_file:
            assert wav_file.getsampwidth() == 2
            chunk = wav_file.readframes(samples_per_chunk)
            while chunk:
                stream.write(chunk)
                chunk = wav_file.readframes(samples_per_chunk)
