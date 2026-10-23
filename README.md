# EcoSound Shift

**A field-robust bioacoustics benchmark and review workspace for bird-call detection in urban soundscapes.**

The project asks a technical question: does a detector trained largely on public recordings remain reliable on locally collected, noisy audio from unseen sites? It pairs an interactive BirdNET review tool with a reproducible event-level evaluation pipeline. See [the project design](docs/PROJECT_DESIGN.md) for the research protocol, anti-leakage rules, and planned experiments.

## What makes this a research-grade portfolio project

- **Manually reviewed ground truth:** model suggestions are never treated as confirmed labels by themselves.
- **Unseen-site evaluation:** keep entire field sites out of training and threshold selection.
- **Event-level scoring:** detections must match the reviewed species and call interval, not only a recording label.
- **Domain-shift analysis:** report results by site type and field-noise condition.
- **Auditable errors:** every false positive and missed call is written with its recording ID and timestamp.

The original interactive app is currently branded **Vizag Bird Finder** because it was built for recordings around Visakhapatnam. It is one component of EcoSound Shift, not the scientific evaluation itself.

## Field dataset contract

Start from the templates in [`templates/`](templates/):

- `recordings.csv` registers each field recording and its site/noise context.
- `annotations.csv` holds timestamped, manually reviewed events.
- `predictions.csv` stores detector output in a model-neutral format.

Run event-level evaluation once you have reviewed annotations and detector predictions:

```powershell
.\.venv311\Scripts\python.exe -m ecosound_eval.event_evaluation `
  --recordings data/recordings.csv `
  --annotations data/annotations.csv `
  --predictions results/birdnet_predictions.csv `
  --output results/event_eval `
  --minimum-confidence 0.50 `
  --iou-threshold 0.50
```

This writes `event_metrics.json` with precision, recall, and F1 overall and by species, site type, and noise level; `event_matches.csv` makes each error reviewable.

BirdNET Analyzer's timestamped CSV can be converted into the project prediction contract without editing it by hand:

```powershell
.\.venv311\Scripts\python.exe -m ecosound_eval.birdnet_export `
  --input results/recording-001.BirdNET.results.csv `
  --recording-id vizag-park-001 `
  --output results/birdnet_predictions.csv
```

For collection, labelling, licensing, and privacy expectations, read the [dataset card](docs/DATASET_CARD.md) and [annotation guide](docs/ANNOTATION_GUIDE.md).

## Interactive review workspace

## Use the website

Open [vizag-bird-finder.streamlit.app](https://vizag-bird-finder.streamlit.app/). Choose **Upload a recording** or **Record a sound**, add a short clip, and select **Find birds** for a BirdNET suggestion. CSV and JSON downloads are available under detections.

The **Bird calls** panel searches Wikimedia Commons recordings, plays them, and links to the original audio file and its license page. Results are filtered to recordings with a supported reuse license and show creator attribution. They are reference examples from the wider range, not necessarily recordings made in Vizag. The regional list link currently refers to the former Visakhapatnam district and is an older checklist; it is a discovery aid, not a claim that every listed species is resident in the current district.

The app also offers **Train a simple local bird model**. It fits an MFCC + Random Forest classifier from a ZIP you upload. This project's repository does not contain a curated training set, so no built-in learned species model or complete regional audio collection is claimed. A prediction from the uploaded model is a nearest learned class, not a validated identification or calibrated probability. The model exists only in your current Streamlit session.

### Prepare and use a training ZIP

Use real, labeled recordings you are allowed to use. Put `manifest.csv` at the ZIP root and keep audio paths relative to it. Use the scientific name as `label`, and assign the same `recording_id` to every clip cut from one original recording. At least two species and two distinct original recordings per species are required.

```csv
audio_path,label,recording_id
audio/housecrow_01.ogg,Corvus splendens,field-session-01
audio/housecrow_02.ogg,Corvus splendens,field-session-02
audio/koel_01.wav,Eudynamys scolopaceus,field-session-03
audio/koel_02.wav,Eudynamys scolopaceus,field-session-04
```

Zip the manifest and `audio/` folder together, then upload it in the training panel. Keep a separate credits file for downloaded recordings, and follow each file's license (including attribution and share-alike requirements). Example search links in the app do not automatically become part of your training data.

Blank CSV templates are in [`templates/manifest.csv`](templates/manifest.csv) and [`templates/recording_credits.csv`](templates/recording_credits.csv). The credits sheet records each sound's source, contributor, license, and location separately from the model label. Do not treat an unverified species label as ground truth.

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

The command-line pipeline remains available for a BirdNET versus MFCC comparison, using the same held-out recordings for both systems. The repository does not include a labeled audio collection or experiment results.

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
