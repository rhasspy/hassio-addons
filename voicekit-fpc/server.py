#!/usr/bin/env python3
import argparse
import logging
import wave
from datetime import datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


class MyHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, output_dir: Path, **kwargs):
        self.output_dir = output_dir
        super().__init__(*args, **kwargs)

    def do_POST(self):
        self.send_response(200)
        self.end_headers()

        length = int(self.headers["Content-Length"])
        wav_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".wav"
        wav_path = self.output_dir / wav_name
        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setframerate(16000)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)
            wav_file.writeframes(self.rfile.read(length))

        _LOGGER.info("Wrote %s", wav_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=11223)
    parser.add_argument("--output-dir", default=Path.cwd())
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _LOGGER.info("Running server: %s:%s", args.host, args.port)
    httpd = HTTPServer(
        (args.host, args.port), partial(MyHandler, output_dir=output_dir)
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
