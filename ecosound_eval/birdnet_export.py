"""Convert BirdNET Analyzer's timestamped CSV into EcoSound Shift predictions."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


OUTPUT_FIELDS = ["recording_id", "start_seconds", "end_seconds", "scientific_name", "confidence", "model_name"]


def _column(fieldnames: list[str] | None, choices: tuple[str, ...]) -> str | None:
    by_normalized = {(name or "").strip().lower(): name for name in (fieldnames or [])}
    return next((by_normalized[choice] for choice in choices if choice in by_normalized), None)


def export_birdnet_csv(source: Path, destination: Path, recording_id: str, model_name: str = "BirdNET") -> int:
    if not recording_id.strip():
        raise ValueError("recording_id is required")
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        scientific = _column(reader.fieldnames, ("scientific name", "species"))
        confidence = _column(reader.fieldnames, ("confidence", "score"))
        start = _column(reader.fieldnames, ("start (s)", "start_seconds"))
        end = _column(reader.fieldnames, ("end (s)", "end_seconds"))
        if not all((scientific, confidence, start, end)):
            raise ValueError("BirdNET CSV needs Scientific name, Confidence, Start (s), and End (s) columns")
        rows = []
        for row in reader:
            try:
                start_value, end_value, confidence_value = float(row[start]), float(row[end]), float(row[confidence])
            except (TypeError, ValueError) as error:
                raise ValueError("BirdNET CSV contains a non-numeric time or confidence value") from error
            rows.append({"recording_id": recording_id, "start_seconds": start_value, "end_seconds": end_value,
                         "scientific_name": row[scientific].strip(), "confidence": confidence_value,
                         "model_name": model_name})
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert a timestamped BirdNET result CSV to the EcoSound Shift prediction schema")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--recording-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-name", default="BirdNET")
    args = parser.parse_args(argv)
    count = export_birdnet_csv(args.input, args.output, args.recording_id, args.model_name)
    print(f"Wrote {count} predictions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
