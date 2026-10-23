# EcoSound Shift: field-robust bird-call detection

## Portfolio claim

This project measures and improves bird-call detection on field recordings that differ from the public audio used to train most recognition systems. It does not claim that an unreviewed model suggestion is a confirmed occurrence record.

## Research question

How does a bird-call detector's event-level performance change across local sites and acoustic-noise conditions, and does local fine-tuning or noise augmentation reduce that degradation?

## Data design

Use three linked but separate data assets:

1. `recordings.csv` is the registry of field audio, site, device, weather, and recording-level noise condition.
2. `annotations.csv` contains manually reviewed call events. Only `review_status=accepted` is treated as ground truth.
3. `predictions.csv` contains detector outputs with event boundaries, scientific names, confidence, and model name.

Templates are in `templates/`. Audio files and the field dataset stay out of Git because they may be large, sensitive, or have restrictive licenses.

## Collection protocol

Collect at least 12 hours across six or more sites spanning quiet urban green spaces and road-adjacent habitat. Use a fixed 20-minute dawn window per visit, record device and placement, and label recording-level noise as `quiet`, `moderate`, or `high`. For a credible independent test set, reserve entire sites before training: no recording from a held-out site may be used for model fitting, threshold tuning, or augmentation selection.

Manually review 300-500 five-second to ten-second regions, including negative examples. Annotate only species you can support by listening and visual spectrogram inspection; mark uncertain events as `uncertain`, not `accepted`.

## Modelling experiments

1. Evaluate BirdNET output unchanged on held-out local sites.
2. Train an MFCC + Random Forest baseline using recording-disjoint data.
3. Fine-tune or train a stronger embedding classifier with and without noise augmentation.
4. Select thresholds on validation sites only, then run one final unseen-site evaluation.
5. Calibrate confidence on the validation partition and report calibration separately from detection performance.

## Evaluation

Use event-level matching. A prediction is a true positive only when scientific name, recording ID, and temporal intersection-over-union all match an accepted annotation. The default IoU threshold is 0.5. Report precision, recall, F1, false positives, and false negatives overall and by species, site type, and recording-noise level.

`ecosound-event-evaluate` writes an auditable JSON report and a row-level matching file. Every error can be traced back to a recording and timestamp for review.

## Deliverables

- Reproducible Python package and command-line evaluation tool
- Dataset card and annotation guide
- Experiment configuration and held-out-site protocol
- Interactive Streamlit review interface
- Model card with limitations, licences, and intended use
- Short technical report with robustness and error-analysis figures

## What success looks like

A credible outcome is a transparent benchmark, even if the model performs poorly in high-noise audio. The portfolio value is in showing where the model generalizes, how the result was measured, and whether a documented intervention improved it.
