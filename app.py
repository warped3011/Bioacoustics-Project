"""Local Streamlit website for the EcoSound AI research evaluation pipeline."""

from __future__ import annotations

import tempfile
import json
import zipfile
from pathlib import Path, PurePosixPath

import pandas as pd
import streamlit as st

from ecosound_eval.identify import identify_audio
from ecosound_eval.pipeline import read_manifest, run

st.set_page_config(page_title="EcoSound AI | Bird Sound ID", page_icon="🐦", layout="wide")
st.title("🐦 EcoSound AI")
st.write("Explore bird sounds with an audio identification tool, or run a controlled research evaluation.")

with st.expander("Identify birds in a sound", expanded=True):
    st.write("Upload a recording or record a short clip. BirdNET returns candidate detections with model confidence scores and timestamps when available.")
    st.caption("Predictions can be wrong, especially with noisy recordings, distant calls, or species outside the model's coverage. Listen and verify before using a detection as a species record.")
    uploaded_audio = st.file_uploader("Choose an audio recording", type=["wav", "mp3", "flac", "ogg"], key="identify_upload")
    recorded_audio = st.audio_input("Or record a bird sound", key="identify_record")
    id_col1, id_col2 = st.columns([1, 1])
    with id_col1:
        minimum_confidence = st.slider("Minimum model confidence", min_value=0.05, max_value=0.90,
                                       value=0.20, step=0.05,
                                       help="This filters displayed BirdNET detections; the score is not a calibrated probability.")
    with id_col2:
        id_threads = st.number_input("CPU threads", min_value=1, max_value=16, value=2, step=1, key="id_threads")
    vizag_filter = st.checkbox("Prioritize species expected near Visakhapatnam", value=True,
                               help="Uses BirdNET location filters at Visakhapatnam coordinates. Rare, seasonal, or unusual visitors may be filtered out.")
    if uploaded_audio is not None:
        st.audio(uploaded_audio)
    elif recorded_audio is not None:
        st.audio(recorded_audio)
    if st.button("Identify sound", type="primary", disabled=uploaded_audio is None and recorded_audio is None):
        st.session_state.pop("ecosound_identification", None)
        sound = uploaded_audio if uploaded_audio is not None else recorded_audio
        suffix = Path(sound.name).suffix.lower() if uploaded_audio is not None else ".wav"
        if suffix not in {".wav", ".mp3", ".flac", ".ogg"}:
            suffix = ".wav"
        try:
            with st.spinner("Analyzing audio with BirdNET… the first run may take longer while model files are prepared."):
                with tempfile.TemporaryDirectory(prefix="ecosound_identify_") as temp:
                    workspace = Path(temp)
                    audio_path = workspace / f"recording{suffix}"
                    audio_path.write_bytes(sound.getvalue())
                    detections = identify_audio(audio_path, workspace / "birdnet_results",
                                                threads=int(id_threads), min_confidence=float(minimum_confidence),
                                                latitude=17.6868 if vizag_filter else None,
                                                longitude=83.2185 if vizag_filter else None)
            st.session_state["ecosound_identification"] = {
                "detections": detections,
                "source_name": uploaded_audio.name if uploaded_audio is not None else "Microphone recording",
                "min_confidence": float(minimum_confidence),
                "vizag_filter": vizag_filter,
            }
        except Exception as exc:
            st.error(f"Could not identify this recording: {exc}")

    identified = st.session_state.get("ecosound_identification")
    if identified:
        detections = identified["detections"]
        location = "Visakhapatnam location filter" if identified["vizag_filter"] else "no location filter"
        st.caption(f"Analysis: {identified['source_name']} · minimum confidence {identified['min_confidence']:.2f} · {location}")
        if not detections:
            st.info("No detections met this confidence threshold. Try a clearer or longer recording, or lower the threshold.")
        else:
            summary = {}
            for detection in detections:
                name = detection["scientific_name"]
                if name not in summary or detection["confidence"] > summary[name]["confidence"]:
                    summary[name] = detection
            st.subheader("Candidate species")
            st.dataframe([{"Scientific name": row["scientific_name"],
                           "Common name": row["common_name"],
                           "Highest segment confidence": row["confidence"]}
                          for row in sorted(summary.values(), key=lambda row: row["confidence"], reverse=True)],
                         use_container_width=True, hide_index=True)
            st.subheader("Detections by audio segment")
            st.dataframe([{"Scientific name": row["scientific_name"], "Common name": row["common_name"],
                            "Confidence": row["confidence"],
                            "Start (s)": row.get("start_seconds"), "End (s)": row.get("end_seconds")}
                           for row in detections], use_container_width=True, hide_index=True)
            result_df = pd.DataFrame(detections)
            csv_data = result_df.to_csv(index=False).encode("utf-8")
            json_data = json.dumps({"minimum_confidence": identified["min_confidence"],
                                    "location_filter": "Visakhapatnam" if identified["vizag_filter"] else None,
                                    "detections": detections}, indent=2).encode("utf-8")
            dl1, dl2 = st.columns(2)
            dl1.download_button("Download detections CSV", csv_data, "bird_detections.csv", "text/csv")
            dl2.download_button("Download detections JSON", json_data, "bird_detections.json", "application/json")
    st.caption("BirdNET-Analyzer source is MIT licensed; its model files are CC BY-NC-SA 4.0. Check the terms for the model you use, especially before commercial use. [Official licensing FAQ](https://birdnet-team.github.io/BirdNET-Analyzer/stable/faq.html) · [Official CLI documentation](https://birdnet-team.github.io/BirdNET-Analyzer/stable/usage/cli.html).")

st.divider()
st.subheader("Research evaluation")
st.write("Compare an MFCC baseline with BirdNET on the same held-out recordings, then examine performance under controlled noise.")
st.info("Evaluation results require your own labeled recordings. Species detections from the tool above are candidates, not verified ground-truth labels.")

with st.expander("Prepare your dataset", expanded=True):
    st.markdown("""
1. Make a `manifest.csv` with columns `audio_path`, `label`, and `recording_id`.
2. Put the audio files in a ZIP archive. Keep the relative paths in the CSV, for example `audio/recording01.wav`.
3. Use one consistent label per species and one stable `recording_id` for each original recording. If you cut one recording into clips, give every clip from it the same ID.
4. Include at least **two different recordings per species** so each class can appear in training and held-out evaluation.

Example manifest:

```csv
audio_path,label,recording_id
audio/blackbird01.wav,Turdus merula,blackbird-session-01
audio/blackbird02.wav,Turdus merula,blackbird-session-02
audio/greattit01.wav,Parus major,greattit-session-01
audio/greattit02.wav,Parus major,greattit-session-02
```
""")

col_data, col_settings = st.columns([1.2, 0.8])
with col_data:
    st.header("1. Add recordings")
    manifest_file = st.file_uploader("Manifest CSV", type=["csv"], help="Required columns: audio_path, label, recording_id")
    archive_file = st.file_uploader("Audio recordings ZIP", type=["zip"], help="ZIP paths must match audio_path entries in the manifest")
with col_settings:
    st.header("2. Choose experiment")
    seed = st.number_input("Random seed", min_value=0, max_value=2_147_483_647, value=42, step=1)
    test_fraction = st.slider("Held-out recording fraction", min_value=0.1, max_value=0.5, value=0.2, step=0.05)
    run_noise = st.checkbox("Include controlled noise conditions")
    noise_snr = st.multiselect("Noise levels (SNR in dB)", options=[30, 20, 10, 5, 0], default=[20, 10], disabled=not run_noise)
    birdnet_threads = st.number_input("BirdNET CPU threads", min_value=1, max_value=64, value=2, step=1)


def safe_extract(archive: zipfile.ZipFile, root: Path) -> None:
    """Extract ordinary files under root; reject traversal and links."""
    root_resolved = root.resolve()
    for info in archive.infolist():
        member = PurePosixPath(info.filename)
        if member.is_absolute() or ".." in member.parts or "\\" in info.filename:
            raise ValueError(f"Unsafe path in ZIP archive: {info.filename}")
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError(f"Symbolic links are not allowed in ZIP archive: {info.filename}")
        destination = (root / Path(*member.parts)).resolve()
        if destination != root_resolved and root_resolved not in destination.parents:
            raise ValueError(f"ZIP member escapes the extraction folder: {info.filename}")
        if info.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, destination.open("wb") as target:
                target.write(source.read())


if st.button("Run evaluation", type="primary", disabled=not (manifest_file is not None and archive_file is not None), use_container_width=True):
    with st.spinner("Checking dataset and running the evaluation…"):
        try:
            with tempfile.TemporaryDirectory(prefix="ecosound_web_") as temp:
                workspace = Path(temp)
                audio_root = workspace / "dataset"
                audio_root.mkdir()
                with zipfile.ZipFile(archive_file) as archive:
                    safe_extract(archive, audio_root)
                dataset_manifest = audio_root / "manifest.csv"
                dataset_manifest.write_bytes(manifest_file.getvalue())
                samples = read_manifest(dataset_manifest)
                species = sorted({sample.label for sample in samples})
                if len(species) < 2:
                    raise ValueError("The evaluation needs at least two species labels.")
                counts = {label: len({s.recording_id for s in samples if s.label == label}) for label in species}
                too_small = [f"{label} ({n} recording(s))" for label, n in counts.items() if n < 2]
                if too_small:
                    raise ValueError("Each species needs at least two distinct recordings: " + ", ".join(too_small))
                result_dir = workspace / "results"
                result = run(dataset_manifest, result_dir, int(seed), float(test_fraction),
                             sorted(set(noise_snr)) if run_noise else [], birdnet_threads=int(birdnet_threads))
                st.session_state["ecosound_result"] = {
                    "json": (result_dir / "results.json").read_bytes(),
                    "csv": (result_dir / "predictions.csv").read_bytes(),
                    "metadata": result,
                }
        except zipfile.BadZipFile:
            st.error("That audio upload is not a readable ZIP file.")
        except Exception as exc:
            st.error(f"Evaluation could not be completed: {exc}")

result_state = st.session_state.get("ecosound_result")
if result_state:
    meta = result_state["metadata"]
    st.header("3. Results")
    st.caption("These metrics come from the completed run shown here; no example or placeholder results are used.")
    summary_cols = st.columns(3)
    summary_cols[0].metric("Held-out recordings", len(meta["heldout_recordings"]))
    summary_cols[1].metric("Species labels", len(meta["labels"]))
    summary_cols[2].metric("Conditions", len(meta["conditions"]))
    for condition, values in meta["conditions"].items():
        with st.expander(f"{condition} · {values['n_recordings']} recordings", expanded=True):
            a, b = st.columns(2)
            a.metric("MFCC accuracy", f"{values['mfcc_accuracy']:.3f}")
            b.metric("BirdNET accuracy", f"{values['birdnet_accuracy']:.3f}")
            st.markdown("**Per-species recall and errors**")
            st.dataframe([{"Species": label, "Recordings": row["n"], "MFCC recall": row["mfcc_recall"],
                           "BirdNET recall": row["birdnet_recall"], "MFCC error IDs": ", ".join(row["mfcc_errors"]),
                           "BirdNET error IDs": ", ".join(row["birdnet_errors"])}
                          for label, row in values["per_species"].items()], use_container_width=True, hide_index=True)
            st.markdown("**MFCC confusion matrix**")
            st.dataframe(pd.DataFrame(values["mfcc_confusion_matrix"], index=values["classes"], columns=values["classes"]), use_container_width=True)
            st.caption("BirdNET confusion matrix includes a __NO_DETECTION__ column when no dataset label matches a detection.")
            st.dataframe(pd.DataFrame(values["birdnet_confusion_matrix"], index=values["classes"], columns=values["classes"]), use_container_width=True)
    st.download_button("Download predictions.csv", data=result_state["csv"], file_name="predictions.csv", mime="text/csv")
    st.download_button("Download results.json", data=result_state["json"], file_name="results.json", mime="application/json")

with st.expander("About BirdNET and licensing"):
    st.markdown("""
The site calls BirdNET-Analyzer through its documented command-line interface. BirdNET-Analyzer's source is MIT licensed; its model files are CC BY-NC-SA 4.0. Check the exact model license and your use case before running. [Official CLI documentation](https://birdnet-team.github.io/BirdNET-Analyzer/stable/usage/cli.html) · [License FAQ](https://birdnet-team.github.io/BirdNET-Analyzer/stable/faq.html).

Audio uploads are held in a temporary local folder for the duration of the run and removed afterward. Result CSV/JSON files are kept in this browser session for download.
""")
