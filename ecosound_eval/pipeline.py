from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Sample:
    audio: Path
    label: str
    recording_id: str


def read_manifest(path: Path) -> list[Sample]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"audio_path", "label", "recording_id"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Manifest must have audio_path,label,recording_id columns")
        rows = []
        for row in reader:
            audio = Path(row["audio_path"])
            if not audio.is_absolute():
                audio = (path.parent / audio).resolve()
            if not audio.is_file():
                raise FileNotFoundError(f"Audio file does not exist: {audio}")
            label, rid = row["label"].strip(), row["recording_id"].strip()
            if not label or not rid:
                raise ValueError("Each manifest row needs a non-empty label and recording_id")
            rows.append(Sample(audio, label, rid))
    if not rows:
        raise ValueError("Manifest contains no samples")
    # A recording must have one ground-truth label. Different segments may share its ID.
    labels_by_recording: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        labels_by_recording[row.recording_id].add(row.label)
    conflicts = [key for key, labels in labels_by_recording.items() if len(labels) != 1]
    if conflicts:
        raise ValueError(f"recording_id maps to multiple labels: {', '.join(sorted(conflicts))}")
    return rows


def split_by_recording(samples: list[Sample], test_fraction: float, seed: int) -> tuple[list[Sample], list[Sample]]:
    """Deterministic stratified split where an entire recording stays in one partition."""
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")
    labels: dict[str, str] = {}
    groups: dict[str, list[Sample]] = defaultdict(list)
    for s in samples:
        if s.recording_id in labels and labels[s.recording_id] != s.label:
            raise ValueError(f"Recording {s.recording_id!r} has conflicting labels")
        labels[s.recording_id] = s.label
        groups[s.recording_id].append(s)
    by_label: dict[str, list[str]] = defaultdict(list)
    for rid, label in labels.items():
        by_label[label].append(rid)
    rng = random.Random(seed)
    test_ids: set[str] = set()
    for label, ids in sorted(by_label.items()):
        ids = sorted(ids)
        rng.shuffle(ids)
        if len(ids) < 2:
            raise ValueError(f"Class {label!r} needs at least two distinct recordings for a held-out split")
        n_test = min(len(ids) - 1, max(1, round(len(ids) * test_fraction)))
        test_ids.update(ids[:n_test])
    train = [s for s in samples if s.recording_id not in test_ids]
    test = [s for s in samples if s.recording_id in test_ids]
    if {s.recording_id for s in train} & {s.recording_id for s in test}:
        raise AssertionError("Recording leakage detected")
    return train, test


def _audio(path: Path) -> tuple[np.ndarray, int]:
    try:
        import soundfile as sf
    except ImportError as e:
        raise RuntimeError("Audio support requires soundfile; install ecosound-eval[audio]") from e
    data, rate = sf.read(path, dtype="float32", always_2d=True)
    return data.mean(axis=1), int(rate)


def mfcc_features(path: Path, n_mfcc: int = 20) -> np.ndarray:
    """Mean and standard deviation of MFCCs; scipy is used for the DCT/filterbank."""
    try:
        from scipy.fft import dct
        from scipy.signal import resample_poly
    except ImportError as e:
        raise RuntimeError("MFCC baseline requires scipy; install ecosound-eval[baseline]") from e
    signal, rate = _audio(path)
    if signal.size == 0:
        raise ValueError(f"Empty audio: {path}")
    if rate != 22050:
        divisor = math.gcd(rate, 22050)
        signal = resample_poly(signal, 22050 // divisor, rate // divisor)
        rate = 22050
    frame_len, hop = int(.025 * rate), int(.010 * rate)
    if signal.size < frame_len:
        signal = np.pad(signal, (0, frame_len - signal.size))
    frames = np.lib.stride_tricks.sliding_window_view(signal, frame_len)[::hop]
    frames = frames * np.hamming(frame_len).astype(np.float32)
    spectrum = np.abs(np.fft.rfft(frames, n=512, axis=1)) ** 2
    hz = np.linspace(0, rate / 2, spectrum.shape[1])
    mel = lambda x: 2595 * np.log10(1 + x / 700)
    mel_points = np.linspace(mel(0), mel(rate / 2), 42)
    bins = np.searchsorted(hz, 700 * (10 ** (mel_points / 2595) - 1))
    bank = np.zeros((40, len(hz)), dtype=np.float32)
    for i in range(40):
        left, center, right = bins[i:i + 3]
        if center > left:
            bank[i, left:center] = np.arange(center - left) / (center - left)
        if right > center:
            bank[i, center:right] = (right - np.arange(center, right)) / (right - center)
    energies = np.maximum(spectrum @ bank.T, 1e-10)
    coeff = dct(np.log(energies), type=2, axis=1, norm="ortho")[:, :n_mfcc]
    return np.concatenate([coeff.mean(axis=0), coeff.std(axis=0)]).astype(np.float32)


class BirdNETCLI:
    """Adapter for BirdNET-Analyzer's documented `python -m ...analyze` CLI."""
    def __init__(self, python: str = sys.executable, threads: int = 2, min_conf: float = 0.01):
        self.python, self.threads, self.min_conf = python, threads, min_conf

    def predict(self, sample: Sample, audio_path: Path, workdir: Path) -> tuple[str | None, dict[str, float]]:
        out = workdir / (hashlib.sha256((sample.recording_id + str(audio_path)).encode()).hexdigest()[:16])
        out.mkdir(parents=True, exist_ok=True)
        cmd = [self.python, "-m", "birdnet_analyzer.analyze", str(audio_path), "-o", str(out),
               "--rtype", "csv", "--combine_results", "--threads", str(self.threads),
               "--min_conf", str(self.min_conf), "--locale", "en"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("BirdNET-Analyzer failed. Install the documented package in this Python environment.\n" + result.stderr[-4000:])
        files = list(out.glob("*.csv"))
        if not files:
            raise RuntimeError(f"BirdNET produced no CSV output in {out}; command: {cmd}")
        scores: dict[str, float] = defaultdict(float)
        with files[0].open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fields = {name.lower().strip(): name for name in (reader.fieldnames or [])}
            species_col = next((fields[k] for k in ("scientific name", "species", "label") if k in fields), None)
            conf_col = next((fields[k] for k in ("confidence", "score", "probability") if k in fields), None)
            if not species_col or not conf_col:
                raise RuntimeError(f"Unrecognized BirdNET CSV schema: {reader.fieldnames}")
            for row in reader:
                label = row[species_col].strip()
                try:
                    score = float(row[conf_col])
                except (ValueError, TypeError):
                    continue
                # BirdNET emits repeated time windows. Max score is the recording-level score.
                scores[label] = max(scores[label], score)
        if not scores:
            return None, {}
        return max(scores, key=scores.get), dict(scores)


def _canonical(label: str, candidates: set[str]) -> str | None:
    label = label.strip().casefold()
    exact = next((x for x in candidates if x.casefold() == label), None)
    if exact:
        return exact
    # Analyzer CSV commonly uses `Scientific name_Common name`.
    scientific = label.split("_")[0].casefold()
    return next((x for x in candidates if scientific in {x.casefold(), x.split("_")[0].casefold()}), None)


def _noise_copy(sample: Sample, snr_db: float, seed: int, target: Path) -> Path:
    import soundfile as sf
    data, rate = sf.read(sample.audio, dtype="float32", always_2d=True)
    rng = np.random.default_rng(seed)
    power = float(np.mean(data ** 2))
    noise_power = power / (10 ** (snr_db / 10)) if power > 0 else 0.0
    noisy = np.clip(data + rng.normal(0, math.sqrt(noise_power), data.shape), -1, 1)
    target.parent.mkdir(parents=True, exist_ok=True)
    sf.write(target, noisy, rate)
    return target


def _confusion(truth: list[str], pred: list[str], classes: list[str]) -> list[list[int]]:
    index = {label: i for i, label in enumerate(classes)}
    matrix = [[0 for _ in classes] for _ in classes]
    for actual, guessed in zip(truth, pred):
        matrix[index[actual]][index[guessed]] += 1
    return matrix


def run(manifest: Path, output: Path, seed: int = 42, test_fraction: float = .2,
        snr_db: list[float] | None = None, birdnet_python: str = sys.executable,
        birdnet_threads: int = 2) -> dict[str, Any]:
    from sklearn.ensemble import RandomForestClassifier
    samples = read_manifest(manifest)
    train, heldout = split_by_recording(samples, test_fraction, seed)
    labels = sorted({s.label for s in samples})
    if len(labels) < 2:
        raise ValueError("Evaluation requires at least two species labels")
    clf = RandomForestClassifier(n_estimators=300, random_state=seed, class_weight="balanced")
    clf.fit(np.stack([mfcc_features(s.audio) for s in train]), [s.label for s in train])
    output.mkdir(parents=True, exist_ok=True)
    records = []
    birdnet = BirdNETCLI(birdnet_python, birdnet_threads)
    with tempfile.TemporaryDirectory(prefix="ecosound_eval_") as temp:
        tempdir = Path(temp)
        conditions: list[tuple[str, float | None]] = [("clean", None)] + [(f"noise_{x:g}dB", x) for x in (snr_db or [])]
        for condition, snr in conditions:
            for sample in heldout:
                audio = sample.audio
                if snr is not None:
                    key = hashlib.sha256(f"{seed}:{sample.recording_id}:{snr}".encode()).hexdigest()[:16]
                    audio = _noise_copy(sample, snr, seed, tempdir / "noisy" / key / sample.audio.name)
                mfcc_pred = str(clf.predict(mfcc_features(audio).reshape(1, -1))[0])
                bn_raw, bn_scores = birdnet.predict(sample, audio, tempdir / "birdnet")
                bn_pred = _canonical(bn_raw, set(labels)) if bn_raw else None
                records.append({"recording_id": sample.recording_id, "audio_path": str(sample.audio), "condition": condition,
                                "snr_db": snr, "truth": sample.label, "mfcc_prediction": mfcc_pred,
                                "birdnet_raw_prediction": bn_raw, "birdnet_prediction": bn_pred,
                                "birdnet_scores": bn_scores})
    # Multiple clips from one source recording are pooled to one prediction so
    # each independent recording contributes exactly once to reported metrics.
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[(row["condition"], row["recording_id"])].append(row)
    recording_records = []
    for (condition, recording_id), clips in sorted(grouped.items()):
        mfcc_votes: dict[str, int] = defaultdict(int)
        birdnet_scores: dict[str, float] = defaultdict(float)
        for clip in clips:
            mfcc_votes[clip["mfcc_prediction"]] += 1
            for label, score in clip["birdnet_scores"].items():
                birdnet_scores[label] = max(birdnet_scores[label], score)
        mfcc_pred = sorted(mfcc_votes, key=lambda x: (-mfcc_votes[x], x))[0]
        bn_raw = max(birdnet_scores, key=birdnet_scores.get) if birdnet_scores else None
        recording_records.append({"recording_id": recording_id,
            "audio_path": ";".join(sorted({str(c["audio_path"]) for c in clips})),
            "condition": condition, "snr_db": clips[0]["snr_db"], "truth": clips[0]["truth"],
            "mfcc_prediction": mfcc_pred, "birdnet_raw_prediction": bn_raw,
            "birdnet_prediction": _canonical(bn_raw, set(labels)) if bn_raw else None,
            "birdnet_scores": dict(birdnet_scores)})
    conditions_results = {}
    for cond in sorted({r["condition"] for r in records}):
        subset = [r for r in recording_records if r["condition"] == cond]
        truths = [r["truth"] for r in subset]
        matrix_classes = labels + ["__NO_DETECTION__"]
        bn_mapped = [r["birdnet_prediction"] if r["birdnet_prediction"] in labels else "__NO_DETECTION__" for r in subset]
        result = {"n_recordings": len(subset), "classes": matrix_classes,
                  "mfcc_accuracy": sum(a == b for a, b in zip(truths, [r["mfcc_prediction"] for r in subset])) / len(subset),
                  "birdnet_accuracy": sum(a == b for a, b in zip(truths, [r["birdnet_prediction"] for r in subset])) / len(subset),
                  "mfcc_confusion_matrix": _confusion(truths, [r["mfcc_prediction"] for r in subset], labels),
                  "birdnet_confusion_matrix": _confusion(truths, bn_mapped, matrix_classes),
                  "per_species": {}}
        for label in labels:
            actual = [r for r in subset if r["truth"] == label]
            result["per_species"][label] = {"n": len(actual),
                "mfcc_recall": sum(r["mfcc_prediction"] == label for r in actual) / len(actual),
                "birdnet_recall": sum(r["birdnet_prediction"] == label for r in actual) / len(actual),
                "mfcc_errors": [r["recording_id"] for r in actual if r["mfcc_prediction"] != label],
                "birdnet_errors": [r["recording_id"] for r in actual if r["birdnet_prediction"] != label]}
        conditions_results[cond] = result
    metadata = {"seed": seed, "test_fraction": test_fraction, "split_unit": "recording_id",
                "train_recordings": sorted({s.recording_id for s in train}),
                "heldout_recordings": sorted({s.recording_id for s in heldout}),
                "labels": labels, "birdnet_interface": "python -m birdnet_analyzer.analyze (CSV)",
                "snr_db": snr_db or [], "conditions": conditions_results}
    (output / "results.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    with (output / "predictions.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["recording_id", "audio_path", "condition", "snr_db", "truth", "mfcc_prediction", "birdnet_raw_prediction", "birdnet_prediction", "birdnet_scores"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in recording_records:
            writer.writerow({**row, "birdnet_scores": json.dumps(row["birdnet_scores"], sort_keys=True)})
    return metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recording-aware EcoSound research evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run", help="compare MFCC baseline and BirdNET on held-out recordings")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--test-fraction", type=float, default=.2)
    p.add_argument("--noise-snr", type=float, nargs="*", default=[], metavar="DB")
    p.add_argument("--birdnet-python", default=sys.executable)
    p.add_argument("--birdnet-threads", type=int, default=2)
    args = parser.parse_args(argv)
    result = run(args.manifest, args.output, args.seed, args.test_fraction, args.noise_snr,
                 args.birdnet_python, args.birdnet_threads)
    print(json.dumps({"output": str(args.output), "heldout_recordings": len(result["heldout_recordings"]),
                      "conditions": list(result["conditions"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
