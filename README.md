# Vizag Bird Finder

## Use the website

Open [vizag-bird-finder.streamlit.app](https://vizag-bird-finder.streamlit.app/). Choose **Upload a recording** or **Record a sound**, add a short clip, and select **Find birds**. The results show the strongest candidate, other possible birds, and timestamps for detected segments when BirdNET provides them. CSV and JSON downloads are available under the detections.

The optional settings default to a broad search. Turn on the Visakhapatnam filter to narrow likely species; it can hide rare or seasonal visitors. BirdNET scores are model scores, not probabilities, and detections should be checked by listening to the audio.

The hosted app prepares BirdNET in writable temporary storage so its model checkpoint can be downloaded in restricted hosting environments. The first analysis after a container restart may take longer while the model is prepared; it needs internet access.

## Run locally on Windows

BirdNET-Analyzer's documented command-line setup supports Python 3.10 and 3.11. After installing Python 3.11, open PowerShell in this project folder and run:

```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install --upgrade pip
.\.venv311\Scripts\python.exe -m pip install -e ".[baseline,web,dev,birdnet]"
.\.venv311\Scripts\python.exe -m streamlit run app.py
```

The website opens at `http://localhost:8501`. The first setup and first BirdNET analysis need internet access. BirdNET-Analyzer source code is MIT licensed; its model files are CC BY-NC-SA 4.0. Check the model license before commercial use ([official FAQ](https://birdnet-team.github.io/BirdNET-Analyzer/stable/faq.html)).

## Reproducible research experiments

The website is dedicated to sound identification. The command-line pipeline remains available for a BirdNET versus MFCC comparison, using the same held-out recordings for both systems. The repository does not include a labeled audio collection or experiment results.

Create a UTF-8 `data/manifest.csv` with `audio_path`, `label`, and `recording_id` columns. Audio paths are relative to the manifest. Use one stable recording ID for each original recording; clips cut from one source recording must share its ID. Provide at least two distinct recordings per species to split that species between training and held-out evaluation.

```csv
audio_path,label,recording_id
audio/blackbird_take01.wav,Turdus merula,session-01
audio/blackbird_take02.wav,Turdus merula,session-02
audio/greattit_take01.wav,Parus major,session-03
audio/greattit_take02.wav,Parus major,session-04
```

Clean held-out comparison:

```powershell
.\.venv311\Scripts\python.exe -m ecosound_eval.pipeline run --manifest data/manifest.csv --output results/clean --seed 42 --test-fraction 0.2
```

Controlled noise at 20 dB and 10 dB signal-to-noise ratio:

```powershell
.\.venv311\Scripts\python.exe -m ecosound_eval.pipeline run --manifest data/manifest.csv --output results/noise --seed 42 --test-fraction 0.2 --noise-snr 20 10
```

Each run writes `predictions.csv` and `results.json` with the recording split, per-species errors, confusion matrices, and metrics actually produced by the run. The split is grouped by original recording ID to prevent clips from the same recording leaking between training and evaluation.

## Tests

```powershell
.\.venv311\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv311\Scripts\python.exe -m pytest
```

Tests cover recording-aware splits, manifest validation, BirdNET CSV parsing and CLI invocation, and confusion matrix behavior. They do not run BirdNET or invent evaluation results.

## Deployment

The app is connected to `warped3011/Bioacoustics-Project` on GitHub. For Streamlit Community Cloud, use Python 3.11 in Advanced settings because of BirdNET-Analyzer's supported CLI installation. [Streamlit deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

Audio sent to the hosted website is processed on the app server in a temporary folder and removed after analysis; result downloads stay in the browser session. Do not upload recordings unless you have permission to use them.
