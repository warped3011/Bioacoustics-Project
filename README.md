# EcoSound Shift

**A Vercel-native field-review and evaluation system for bird-call detection in noisy urban audio.**

EcoSound Shift investigates a practical audio-ML question: does a bird-call detector trained mostly on public recordings remain reliable on local field audio from unseen sites and different noise conditions?

## Research workflow

1. Register every field session in `recordings.csv`.
2. Review detector output in a spectrogram and record accepted events in `annotations.csv`.
3. Evaluate predictions with the event-level command below.
4. Report precision, recall, and F1 by species, site type, and field-noise condition.

```powershell
py -3.11 -m pip install -e ".[baseline,birdnet]"
py -3.11 -m ecosound_eval.event_evaluation `
  --recordings data/recordings.csv `
  --annotations data/annotations.csv `
  --predictions results/birdnet_predictions.csv `
  --output results/event_eval
```

The evaluator matches predictions to accepted events by recording ID, scientific name, and temporal intersection-over-union. It creates `event_metrics.json` and `event_matches.csv` for auditable error analysis.

## Vercel architecture

- `public/`: static, responsive research-review client
- `api/analyze.py`: Python Vercel Function running bounded BirdNET analysis
- `ecosound_eval/`: reusable, local research pipeline
- `templates/`: CSV contracts for recording metadata, reviewed events, and detector predictions

The API accepts WAV, MP3, FLAC, and OGG clips under 3 MB. The size limit protects the Vercel request body limit and keeps inference suitable for on-demand review, rather than batch processing.

## Deployment

Import the GitHub repository into Vercel. `vercel.json` configures the BirdNET API function with 2 GB memory and a 300-second maximum duration. The function runs from the `main` branch after each push.

## Documentation

- [Project design](docs/PROJECT_DESIGN.md)
- [Dataset card](docs/DATASET_CARD.md)
- [Annotation guide](docs/ANNOTATION_GUIDE.md)

## Licence and responsible use

The repository does not include a field audio dataset. Keep original source, licence, contributor, and access information for third-party recordings. BirdNET source and model terms are separate; review them before commercial use. Automated detections remain suggestions until independently reviewed.
