# EcoSound AI research evaluation

## Open the website on your computer

The web interface is a local Streamlit app. Install Python 3.10 or 3.11, then from this project folder run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[baseline,web,dev]"
python -m pip install "birdnet-analyzer>=2.4"
python -m streamlit run app.py
```

Streamlit will print a local address, usually `http://localhost:8501`, and may open it in your browser. If PowerShell blocks environment activation, run the venv's Python directly instead: `.\.venv\Scripts\python.exe -m pip install -e ".[baseline,web,dev]"`, then `.\.venv\Scripts\python.exe -m streamlit run app.py`. BirdNET installation needs Python 3.10 or 3.11 per its documented command-line setup. The first installation needs an internet connection. This app runs on the same computer and is not publicly hosted.

On the website, upload the manifest CSV and a ZIP of the audio files, choose a split fraction and optional noise levels, then click **Run evaluation**. After the run finishes, inspect the per-condition metrics and download `predictions.csv` and `results.json`. Use at least two distinct source recording IDs for every species. The upload control has Streamlit's default 200 MB per-file limit. Do not expose the local app to the public internet; it has no authentication. The sample rows below describe format only.

This repository contains a local website and reproducible evaluation module. The initial workspace did not include an existing EcoSound AI application or dataset, so this adds an executable evaluation scaffold rather than modifying an existing application. No experiment has been run or reported here.

## Environment and BirdNET license

Use Python 3.10 or 3.11 for the documented BirdNET-Analyzer CLI installation; the analyzer also has a package installation route that may support newer Python versions. Install EcoSound's baseline dependencies with `python -m pip install -e ".[baseline,dev]"`. Install BirdNET-Analyzer into the same environment with `python -m pip install "birdnet-analyzer>=2.4"`, or provide `--birdnet-python` pointing at the Python interpreter where it is installed. BirdNET processing invokes its documented interface, `python -m birdnet_analyzer.analyze`, and reads its CSV output. It does not import private BirdNET modules.

BirdNET-Analyzer source code is MIT licensed. BirdNET models distributed with the analyzer are CC BY-NC-SA 4.0; verify the terms for the particular model in your installation before use, especially for commercial work. See the [official licensing FAQ](https://birdnet-team.github.io/BirdNET-Analyzer/stable/faq.html) and [installation instructions](https://birdnet-team.github.io/BirdNET-Analyzer/stable/installation.html). This project does not bundle BirdNET or its model files.

Official CLI documentation: [BirdNET-Analyzer command line interface](https://birdnet-team.github.io/BirdNET-Analyzer/stable/usage/cli.html).

## Manifest

Create a UTF-8 CSV with these required columns:

```csv
audio_path,label,recording_id
audio/blackbird_take01.wav,Turdus merula,session-2024-01
audio/blackbird_take02.wav,Turdus merula,session-2024-02
audio/greattit_take01.wav,Parus major,session-2024-03
audio/greattit_take02.wav,Parus major,session-2024-04
```

Paths are resolved relative to the manifest. A recording ID must map to exactly one class. If a source recording has been cut into multiple clips, all its clips must share one recording ID so they remain in a single partition. Supply at least two distinct recording IDs per class. BirdNET's broad label set is mapped to dataset labels by exact match or scientific-name prefix; unmatched predictions count as `__NO_DETECTION__` for confusion matrices and as errors in accuracy and per-species recall. The supplied single-label manifest is intended for recordings with one evaluated reference class per recording; multilabel soundscapes need a multilabel manifest/evaluator before interpreting these metrics.

## Run experiments

Clean held-out comparison (MFCC Random Forest vs BirdNET):

```powershell
python -m ecosound_eval.pipeline run --manifest data/manifest.csv --output results/clean --seed 42 --test-fraction 0.2
```

Add deterministic controlled-noise conditions at 20 dB and 10 dB SNR relative to signal RMS:

```powershell
python -m ecosound_eval.pipeline run --manifest data/manifest.csv --output results/noise --seed 42 --test-fraction 0.2 --noise-snr 20 10
```

To run BirdNET in a separate environment, add `--birdnet-python C:\path\to\birdnet\python.exe`. Run `python -m ecosound_eval.pipeline run --help` for all options. Noise is generated independently per held-out recording and SNR from the evaluation seed; clean and noisy versions use the same test recordings. The same trained MFCC classifier is applied to clean and noisy recordings. BirdNET is run on each corresponding audio file with its documented default location filters disabled (latitude/longitude -1) and a low confidence threshold so model detections are retained for aggregation.

Outputs are `predictions.csv` (one row per held-out recording and condition, with BirdNET scores) and `results.json` (split IDs, configuration, aggregate accuracies, confusion matrices and per-species recall/error recording IDs). No results are committed or fabricated; these files are created only after successful execution.

## Tests

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

Tests cover deterministic recording-level splits, leakage prevention, insufficient per-class groups, manifest validation, BirdNET label mapping, and no-detection confusion handling. Tests do not run or emulate BirdNET and do not assert experimental metrics.
