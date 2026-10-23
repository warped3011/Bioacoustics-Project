"""Event-level evaluation for manually reviewed bioacoustic annotations.

The module deliberately keeps the labels and audio separate.  A detector is
evaluated against reviewed events, while site and noise metadata are taken
from the recording registry.  This makes false positives, missed calls, and
performance under acoustic domain shift auditable.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RECORDING_COLUMNS = {
    "recording_id", "audio_path", "site_id", "site_type", "recorded_at",
    "timezone", "device", "noise_level", "weather", "annotator", "notes",
}
ANNOTATION_COLUMNS = {
    "event_id", "recording_id", "start_seconds", "end_seconds",
    "scientific_name", "common_name", "review_status", "annotator_confidence",
    "noise_label", "notes",
}
PREDICTION_COLUMNS = {
    "recording_id", "start_seconds", "end_seconds", "scientific_name",
    "confidence", "model_name",
}


@dataclass(frozen=True)
class Recording:
    recording_id: str
    site_id: str
    site_type: str
    noise_level: str


@dataclass(frozen=True)
class Event:
    event_id: str
    recording_id: str
    start: float
    end: float
    label: str
    noise_label: str


@dataclass(frozen=True)
class Prediction:
    recording_id: str
    start: float
    end: float
    label: str
    confidence: float
    model_name: str


def _read_rows(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or []))
            raise ValueError(f"{path.name} is missing columns: {', '.join(missing)}")
        return list(reader)


def _number(value: str, field: str, row_id: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{row_id}: {field} must be a number") from error
    if number < 0:
        raise ValueError(f"{row_id}: {field} cannot be negative")
    return number


def read_recordings(path: Path) -> dict[str, Recording]:
    recordings: dict[str, Recording] = {}
    for row in _read_rows(path, RECORDING_COLUMNS):
        recording_id = row["recording_id"].strip()
        if not recording_id or recording_id in recordings:
            raise ValueError("recording_id values must be present and unique")
        site_id, site_type = row["site_id"].strip(), row["site_type"].strip()
        if not site_id or not site_type:
            raise ValueError(f"{recording_id}: site_id and site_type are required")
        recordings[recording_id] = Recording(
            recording_id=recording_id,
            site_id=site_id,
            site_type=site_type,
            noise_level=row["noise_level"].strip().lower() or "unknown",
        )
    if not recordings:
        raise ValueError("recordings.csv is empty")
    return recordings


def read_annotations(path: Path, recordings: dict[str, Recording]) -> list[Event]:
    events: list[Event] = []
    seen: set[str] = set()
    for row in _read_rows(path, ANNOTATION_COLUMNS):
        event_id = row["event_id"].strip()
        if not event_id or event_id in seen:
            raise ValueError("event_id values must be present and unique")
        seen.add(event_id)
        recording_id = row["recording_id"].strip()
        if recording_id not in recordings:
            raise ValueError(f"{event_id}: recording_id is not in recordings.csv")
        status = row["review_status"].strip().lower()
        if status != "accepted":
            continue
        start = _number(row["start_seconds"], "start_seconds", event_id)
        end = _number(row["end_seconds"], "end_seconds", event_id)
        label = row["scientific_name"].strip()
        if end <= start or not label:
            raise ValueError(f"{event_id}: event needs end_seconds > start_seconds and a scientific_name")
        events.append(Event(event_id, recording_id, start, end, label, row["noise_label"].strip().lower() or "unknown"))
    return events


def read_predictions(path: Path, recordings: dict[str, Recording], minimum_confidence: float) -> list[Prediction]:
    if not 0 <= minimum_confidence <= 1:
        raise ValueError("minimum_confidence must be between 0 and 1")
    predictions: list[Prediction] = []
    for index, row in enumerate(_read_rows(path, PREDICTION_COLUMNS), start=2):
        row_id = f"prediction row {index}"
        recording_id = row["recording_id"].strip()
        if recording_id not in recordings:
            raise ValueError(f"{row_id}: recording_id is not in recordings.csv")
        start = _number(row["start_seconds"], "start_seconds", row_id)
        end = _number(row["end_seconds"], "end_seconds", row_id)
        confidence = _number(row["confidence"], "confidence", row_id)
        if end <= start or confidence > 1 or not row["scientific_name"].strip():
            raise ValueError(f"{row_id}: invalid interval, confidence, or scientific_name")
        if confidence >= minimum_confidence:
            predictions.append(Prediction(recording_id, start, end, row["scientific_name"].strip(), confidence, row["model_name"].strip() or "unknown"))
    return predictions


def interval_iou(left_start: float, left_end: float, right_start: float, right_end: float) -> float:
    intersection = max(0.0, min(left_end, right_end) - max(left_start, right_start))
    union = max(left_end, right_end) - min(left_start, right_start)
    return intersection / union if union else 0.0


def _metrics(true_positive: int, false_positive: int, false_negative: int) -> dict[str, float | int]:
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    return {
        "true_positives": true_positive,
        "false_positives": false_positive,
        "false_negatives": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
    }


def evaluate(events: list[Event], predictions: list[Prediction], recordings: dict[str, Recording], iou_threshold: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not 0 < iou_threshold <= 1:
        raise ValueError("iou_threshold must be in (0, 1]")
    unmatched_events = set(range(len(events)))
    matches: list[dict[str, Any]] = []
    correct, incorrect = [], []
    for prediction in sorted(predictions, key=lambda item: item.confidence, reverse=True):
        candidates = [
            (interval_iou(prediction.start, prediction.end, event.start, event.end), index)
            for index, event in enumerate(events)
            if index in unmatched_events and event.recording_id == prediction.recording_id and event.label == prediction.label
        ]
        best_iou, event_index = max(candidates, default=(0.0, None))
        context = recordings[prediction.recording_id]
        row = {
            "recording_id": prediction.recording_id, "site_id": context.site_id,
            "site_type": context.site_type, "recording_noise_level": context.noise_level,
            "scientific_name": prediction.label, "prediction_start_seconds": prediction.start,
            "prediction_end_seconds": prediction.end, "confidence": prediction.confidence,
            "model_name": prediction.model_name, "match_status": "false_positive", "iou": best_iou,
        }
        if event_index is not None and best_iou >= iou_threshold:
            event = events[event_index]
            unmatched_events.remove(event_index)
            row.update({"match_status": "true_positive", "event_id": event.event_id,
                        "event_start_seconds": event.start, "event_end_seconds": event.end,
                        "annotation_noise_label": event.noise_label})
            correct.append(row)
        else:
            incorrect.append(row)
        matches.append(row)
    for index in sorted(unmatched_events):
        event = events[index]
        context = recordings[event.recording_id]
        matches.append({"recording_id": event.recording_id, "site_id": context.site_id,
                        "site_type": context.site_type, "recording_noise_level": context.noise_level,
                        "scientific_name": event.label, "event_id": event.event_id,
                        "event_start_seconds": event.start, "event_end_seconds": event.end,
                        "annotation_noise_label": event.noise_label, "match_status": "false_negative"})
    def grouped_metric(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, float | int]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[str(row.get(key, "unknown"))].append(row)
        output = {}
        for name, group in sorted(groups.items()):
            output[name] = _metrics(
                sum(row["match_status"] == "true_positive" for row in group),
                sum(row["match_status"] == "false_positive" for row in group),
                sum(row["match_status"] == "false_negative" for row in group),
            )
        return output
    report = {
        "iou_threshold": iou_threshold,
        "n_recordings": len(recordings), "n_accepted_events": len(events), "n_predictions": len(predictions),
        "overall": _metrics(len(correct), len(incorrect), len(unmatched_events)),
        "by_species": grouped_metric(matches, "scientific_name"),
        "by_site_type": grouped_metric(matches, "site_type"),
        "by_recording_noise_level": grouped_metric(matches, "recording_noise_level"),
    }
    return report, matches


def write_evaluation(output: Path, report: dict[str, Any], matches: list[dict[str, Any]]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "event_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    fields = sorted({field for match in matches for field in match})
    with (output / "event_matches.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(matches)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate time-stamped predictions against reviewed bird-call events")
    parser.add_argument("--recordings", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-confidence", type=float, default=0.5)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    args = parser.parse_args(argv)
    recordings = read_recordings(args.recordings)
    events = read_annotations(args.annotations, recordings)
    predictions = read_predictions(args.predictions, recordings, args.minimum_confidence)
    report, matches = evaluate(events, predictions, recordings, args.iou_threshold)
    write_evaluation(args.output, report, matches)
    print(json.dumps(report["overall"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
