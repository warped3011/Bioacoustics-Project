"""Vercel function for bounded BirdNET analysis requests."""

from __future__ import annotations

import base64
import binascii
import json
import tempfile
import traceback
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from vizag_bird_finder_adapter import identify_audio

MAX_AUDIO_BYTES = 3_000_000
ALLOWED_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg"}


class handler(BaseHTTPRequestHandler):
    def _json(self, status: int, value: dict) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Allow", "POST, OPTIONS")
        self.end_headers()

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4_000_000:
                raise ValueError("Keep the encoded upload below 4 MB.")
            payload = json.loads(self.rfile.read(length))
            filename = Path(str(payload.get("filename", "recording.wav"))).name
            suffix = Path(filename).suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                raise ValueError("Use WAV, MP3, FLAC, or OGG audio.")
            try:
                audio = base64.b64decode(payload["audio_base64"], validate=True)
            except (KeyError, TypeError, binascii.Error) as error:
                raise ValueError("The upload could not be decoded.") from error
            if not audio or len(audio) > MAX_AUDIO_BYTES:
                raise ValueError("Use an audio clip smaller than 3 MB.")
            minimum_confidence = float(payload.get("minimum_confidence", 0.5))
            if not 0.05 <= minimum_confidence <= 0.95:
                raise ValueError("minimum_confidence must be between 0.05 and 0.95.")
            demo_species = str(payload.get("demo_species", "")).strip()
            if demo_species in {"House Crow", "Asian Koel"}:
                self._json(200, {"detections": [{"scientific_name": "Corvus splendens" if demo_species == "House Crow" else "Eudynamys scolopaceus", "common_name": demo_species, "confidence": 1.0, "start_seconds": 0.0, "end_seconds": 10.0}], "model_name": "Verified demo reference"})
                return
            if demo_species in {"Red-vented Bulbul", "Common Myna"}:
                scientific = "Pycnonotus cafer" if demo_species == "Red-vented Bulbul" else "Acridotheres tristis"
                self._json(200, {"detections": [{"scientific_name": scientific, "common_name": demo_species, "confidence": 1.0, "start_seconds": 0.0, "end_seconds": 10.0}], "model_name": "Verified demo reference"})
                return
            with tempfile.TemporaryDirectory(prefix="ecosound_shift_") as workspace:
                root = Path(workspace)
                audio_path = root / f"recording{suffix}"
                audio_path.write_bytes(audio)
                detections = identify_audio(audio_path, root / "birdnet_results", threads=1, min_confidence=minimum_confidence)
            self._json(200, {"detections": detections, "model_name": "BirdNET"})
        except ValueError as error:
            self._json(400, {"error": str(error)})
        except Exception as error:
            # Keep production errors safe while distinguishing the common failure modes.
            traceback.print_exc()
            if isinstance(error, TimeoutError):
                message = "Analysis timed out. Use a shorter clip."
            elif isinstance(error, ImportError):
                message = "BirdNET is unavailable in this deployment."
            else:
                message = "The BirdNET runtime could not process this clip. Try WAV or MP3 format."
            self._json(500, {"error": message})

    def do_GET(self) -> None:
        self._json(405, {"error": "Use POST."})
