# Annotation guide

## Before annotation

Listen with headphones and use a spectrogram. Create one `recordings.csv` row for every audio file before adding events. Use a stable `recording_id`; filenames can change, identifiers must not.

## Event boundaries

Create an event for one continuous, identifiable vocalization. Start at the first visible/audible call energy and end at the last. If a call repeats after a clear gap, make a second event. Overlapping species are separate events.

## Labels

Use scientific names consistently, for example `Corvus splendens`. `common_name` is for readability only. If you cannot identify the caller with sufficient evidence, leave the scientific name blank and set `review_status=uncertain`; this row will not become ground truth.

## Review statuses

- `accepted`: suitable for evaluation.
- `uncertain`: keep for later review; excluded from metrics.
- `rejected`: a non-target sound, duplicate, or annotation mistake; excluded from metrics.

## Noise labels

Use the dominant interference within the event: `traffic`, `wind`, `rain`, `human`, `insects`, `overlap`, `quiet`, or `unknown`. Record-level `noise_level` describes the whole session and should be `quiet`, `moderate`, `high`, or `unknown`.

## Quality control

Blindly re-annotate at least 10% of accepted events after a few days, or ask a second reviewer to inspect them. Record disagreements in the notes field. Do not edit model outputs in place; preserve the original prediction file and evaluate a copied, standard-format export.
