# Dataset card: local urban bird-call events

## Purpose

This dataset supports evaluation of automated bird-call detection under local acoustic conditions. It is not a complete biodiversity inventory and should not be used to infer species abundance, occupancy, or conservation status without an appropriate survey design.

## Unit of data

The primary unit is a manually reviewed vocal event: one interval in one audio recording with a scientific-name label. Each event links to a recording registry row with site and noise metadata.

## Recommended scope

Record 20-minute dawn sessions at six or more sites across at least six visits. Include several quiet green sites and several road-adjacent sites. Aim for 300–500 reviewed clips including difficult and negative examples. The public repository must contain only metadata, documentation, synthetic examples, or audio that is explicitly licensed for redistribution.

## Labelling policy

`accepted` requires a reviewer to support the identity by listening and inspecting the spectrogram. Use `uncertain` whenever the species, boundary, or sound source cannot be supported. Uncertain items stay in the CSV for auditability but are excluded from evaluation. Never copy a model prediction into `accepted` without independent review.

## Data limitations

Phone and consumer recorder amplitude values are uncalibrated. Do not interpret waveform level as sound pressure level. Wind, rain, overlapping animals, distance, microphone placement, and local species coverage can all affect detection performance.

## Splitting rule

Hold out entire sites for the final test partition. All recordings, clips, and augmentations from a held-out site must remain out of training, model selection, and calibration. This protects against optimistic results caused by repeated background sound from the same site.

## Licensing and privacy

Record only where permitted. Do not publish precise coordinates for sensitive taxa or private land. Keep source URL, contributor, licence, and access date for every third-party recording. Follow the BirdNET model licence separately from this project code.
