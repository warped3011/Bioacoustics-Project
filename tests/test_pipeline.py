import csv
from pathlib import Path

import pytest

from ecosound_eval.pipeline import Sample, _canonical, _confusion, read_manifest, split_by_recording


def samples():
    return [Sample(Path(f"{label}-{i}.wav"), label, f"{label}-recording-{i}")
            for label in ("Turdus merula", "Parus major") for i in range(5)]


def test_split_is_deterministic_and_recording_disjoint():
    first = split_by_recording(samples(), .2, 17)
    second = split_by_recording(samples(), .2, 17)
    train, test = first
    assert {x.recording_id for x in train}.isdisjoint({x.recording_id for x in test})
    assert {x.recording_id for x in test} == {x.recording_id for x in second[1]}
    assert {x.label for x in test} == {"Turdus merula", "Parus major"}


def test_split_refuses_single_recording_class():
    with pytest.raises(ValueError, match="at least two distinct recordings"):
        split_by_recording([Sample(Path("a.wav"), "bird", "only")], .2, 1)


def test_manifest_rejects_multiple_labels_for_recording(tmp_path):
    audio = tmp_path / "a.wav"
    audio.touch()
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("audio_path,label,recording_id\na.wav,bird,rec\na.wav,other,rec\n")
    with pytest.raises(ValueError, match="multiple labels"):
        read_manifest(manifest)


def test_birdnet_scientific_label_maps_to_dataset_label():
    assert _canonical("Turdus merula_Common Blackbird", {"Turdus merula", "Parus major"}) == "Turdus merula"
    assert _canonical("Unknown species_Name", {"Turdus merula"}) is None


def test_confusion_matrix_preserves_no_detection_column():
    labels = ["bird", "other", "__NO_DETECTION__"]
    assert _confusion(["bird", "other"], ["__NO_DETECTION__", "other"], labels) == [
        [0, 0, 1], [0, 1, 0], [0, 0, 0]]
