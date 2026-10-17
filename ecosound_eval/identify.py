"""Small adapter for BirdNET-Analyzer's documented file-analysis CLI."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_detections(path: Path) -> list[dict[str, Any]]:
    """Read BirdNET's CSV export without fabricating detections or scores."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = {str(name).strip().casefold(): name for name in (reader.fieldnames or [])}

        def column(*names: str) -> str | None:
            return next((columns[name.casefold()] for name in names if name.casefold() in columns), None)

        species_col = column("Scientific name", "Species", "Label")
        common_col = column("Common name")
        confidence_col = column("Confidence", "Score", "Probability")
        start_col = column("Start (s)", "Start", "Begin (s)")
        end_col = column("End (s)", "End", "Stop (s)")
        if not species_col or not confidence_col:
            raise ValueError(f"Unrecognized BirdNET CSV columns: {reader.fieldnames}")

        detections: list[dict[str, Any]] = []
        for row in reader:
            try:
                confidence = float(row[confidence_col])
            except (TypeError, ValueError):
                continue
            scientific = (row.get(species_col) or "").strip()
            if not scientific:
                continue
            common = (row.get(common_col) or "").strip() if common_col else ""
            item: dict[str, Any] = {
                "scientific_name": scientific,
                "common_name": common,
                "confidence": confidence,
            }
            for key, name in (("start_seconds", start_col), ("end_seconds", end_col)):
                if name:
                    try:
                        item[key] = float(row[name])
                    except (TypeError, ValueError):
                        pass
            detections.append(item)
    return sorted(detections, key=lambda item: item["confidence"], reverse=True)


def identify_audio(audio_path: Path, output_dir: Path, *, threads: int = 2,
                   min_confidence: float = 0.2, python: str | None = None,
                   latitude: float | None = None, longitude: float | None = None) -> list[dict[str, Any]]:
    """Analyze an audio file using BirdNET-Analyzer's public command-line interface."""
    if not 0.00001 <= min_confidence <= 0.99:
        raise ValueError("Minimum confidence must be between 0.00001 and 0.99")
    if threads < 1:
        raise ValueError("Threads must be at least one")
    if (latitude is None) != (longitude is None):
        raise ValueError("Latitude and longitude must be provided together")
    if latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Latitude or longitude is out of range")
    audio_path = audio_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    executable = python or os.environ.get("BIRDNET_PYTHON") or sys.executable
    command = [executable, "-m", "birdnet_analyzer.analyze", str(audio_path),
               "-o", str(output_dir), "--rtype", "csv", "--combine_results",
               "--threads", str(threads), "--min_conf", str(min_confidence), "--locale", "en"]
    if latitude is not None and longitude is not None:
        command.extend(["--lat", str(latitude), "--lon", str(longitude), "--week", "-1"])
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Python executable not found: {executable}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("BirdNET analysis exceeded the 15-minute time limit.") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout)[-4000:]
        raise RuntimeError("BirdNET-Analyzer could not analyze this file. Confirm it is installed "
                           "in the app's Python environment and the audio format is supported.\n" + detail)
    csv_files = sorted(output_dir.glob("*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not csv_files:
        raise RuntimeError("BirdNET finished without producing a CSV detection file.")
    return parse_detections(csv_files[0])
