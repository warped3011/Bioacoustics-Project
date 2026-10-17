import subprocess
from pathlib import Path

import pytest

from vizag_bird_finder_adapter import identify_audio, parse_detections


def test_parse_birdnet_cli_csv_with_timestamps(tmp_path):
    csv_file = tmp_path / "detections.csv"
    csv_file.write_text(
        "Start (s),End (s),Scientific name,Common name,Confidence\n"
        "0.0,3.0,Passer domesticus,House Sparrow,0.82\n"
        "3.0,6.0,Corvus splendens,House Crow,0.41\n",
        encoding="utf-8",
    )

    detections = parse_detections(csv_file)

    assert detections == [
        {"scientific_name": "Passer domesticus", "common_name": "House Sparrow",
         "confidence": 0.82, "start_seconds": 0.0, "end_seconds": 3.0},
        {"scientific_name": "Corvus splendens", "common_name": "House Crow",
         "confidence": 0.41, "start_seconds": 3.0, "end_seconds": 6.0},
    ]


def test_identify_calls_documented_analyzer_cli_and_reads_csv(tmp_path, monkeypatch):
    audio = tmp_path / "bird.wav"
    audio.touch()
    output = tmp_path / "output"
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        output.mkdir(parents=True, exist_ok=True)
        (output / "combined.csv").write_text(
            "Scientific name,Common name,Confidence\nTurdus merula,Common Blackbird,0.9\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("vizag_bird_finder_adapter.subprocess.run", fake_run)
    detections = identify_audio(audio, output, python="python-test", threads=3, min_confidence=0.3,
                                latitude=17.6868, longitude=83.2185)

    command = captured["command"]
    assert command[:3] == ["python-test", "-m", "birdnet_analyzer.analyze"]
    assert "--rtype" in command and "csv" in command
    assert "--combine_results" in command
    assert command[command.index("--lat") + 1] == "17.6868"
    assert command[command.index("--lon") + 1] == "83.2185"
    assert detections[0]["scientific_name"] == "Turdus merula"
    assert captured["kwargs"]["timeout"] == 900


def test_identify_ignores_auxiliary_settings_csv_and_reads_nested_results(tmp_path, monkeypatch):
    audio = tmp_path / "bird.wav"
    audio.touch()
    output = tmp_path / "output"

    def fake_run(command, **kwargs):
        (output / "nested").mkdir(parents=True, exist_ok=True)
        (output / "analysis.csv").write_text(
            "File splitting duration,Segment length,Sample rate,Segment overlap\n5,3,48000,0\n",
            encoding="utf-8",
        )
        (output / "nested" / "combined.BirdNET.results.csv").write_text(
            "Start (s),End (s),Scientific name,Common name,Confidence\n"
            "0,3,Passer domesticus,House Sparrow,0.78\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("vizag_bird_finder_adapter.subprocess.run", fake_run)
    detections = identify_audio(audio, output)

    assert len(detections) == 1
    assert detections[0]["common_name"] == "House Sparrow"


def test_identify_returns_empty_when_only_auxiliary_csv_is_produced(tmp_path, monkeypatch):
    audio = tmp_path / "bird.wav"
    audio.touch()
    output = tmp_path / "output"

    def fake_run(command, **kwargs):
        output.mkdir(parents=True, exist_ok=True)
        (output / "settings.csv").write_text(
            "File splitting duration,Segment length,Sample rate\n5,3,48000\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("vizag_bird_finder_adapter.subprocess.run", fake_run)

    assert identify_audio(audio, output) == []


def test_identify_does_not_surface_unrecognized_result_schema(tmp_path, monkeypatch):
    audio = tmp_path / "bird.wav"
    audio.touch()
    output = tmp_path / "output"

    def fake_run(command, **kwargs):
        output.mkdir(parents=True, exist_ok=True)
        (output / "recording.BirdNET.results.csv").write_text(
            "Scientific name,Confidence\nPasser domesticus,0.7\n", encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    def unexpected_schema(_path):
        raise ValueError("Unrecognized BirdNET CSV columns: ['File splitting duration']")

    monkeypatch.setattr("vizag_bird_finder_adapter.subprocess.run", fake_run)
    monkeypatch.setattr("vizag_bird_finder_adapter.parse_detections", unexpected_schema)

    assert identify_audio(audio, output) == []


def test_identify_rejects_out_of_range_confidence(tmp_path):
    with pytest.raises(ValueError, match="between"):
        identify_audio(Path("audio.wav"), tmp_path, min_confidence=1.0)


def test_identify_requires_latitude_and_longitude_together(tmp_path):
    with pytest.raises(ValueError, match="provided together"):
        identify_audio(Path("audio.wav"), tmp_path, latitude=17.7)


def test_parse_rejects_unrecognized_csv(tmp_path):
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("Animal,Certainty\nBird,0.5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unrecognized BirdNET CSV columns"):
        parse_detections(csv_file)