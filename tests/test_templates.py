import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def columns(path):
    with path.open(newline="", encoding="utf-8") as source:
        return next(csv.reader(source))


def test_manifest_template_matches_pipeline_inputs():
    assert columns(ROOT / "templates" / "manifest.csv") == ["audio_path", "label", "recording_id"]


def test_recording_credits_template_tracks_license_provenance():
    headings = columns(ROOT / "templates" / "recording_credits.csv")
    assert {"recording_id", "source_page", "creator", "license", "license_url"}.issubset(headings)
