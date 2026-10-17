"""Simple Streamlit bird sound identifier for Visakhapatnam."""

from __future__ import annotations

import csv
import io
import json
import tempfile
from pathlib import Path

import streamlit as st

from vizag_bird_finder_adapter import identify_audio


st.set_page_config(page_title="Vizag Bird Finder", page_icon="🐦", layout="centered")

st.title("🐦 Vizag Bird Finder")
st.write("Find likely birds in a recording from Visakhapatnam.")
st.info("Add a short bird sound below. Results are AI suggestions: please listen and verify before treating a bird as identified.")

input_method = st.radio("How would you like to add a sound?", ["Upload a recording", "Record a sound"], horizontal=True)
if input_method == "Upload a recording":
    sound = st.file_uploader("Choose an audio file", type=["wav", "mp3", "flac", "ogg"])
else:
    sound = st.audio_input("Record a bird sound")

if sound is not None:
    st.audio(sound)

with st.expander("Optional settings"):
    minimum_confidence = st.slider(
        "Minimum detection score",
        min_value=0.05,
        max_value=0.90,
        value=0.20,
        step=0.05,
        help="Lower the score to show more possible matches. Scores are not probabilities.",
    )
    vizag_filter = st.checkbox(
        "Focus on birds expected near Vizag",
        value=True,
        help="This can filter out rare, seasonal, or unusual visitors. Turn it off to search more broadly.",
    )

if st.button("Find birds", type="primary", disabled=sound is None, use_container_width=True):
    st.session_state.pop("vizag_bird_result", None)
    suffix = Path(getattr(sound, "name", "recording.wav")).suffix.lower() or ".wav"
    if suffix not in {".wav", ".mp3", ".flac", ".ogg"}:
        suffix = ".wav"
    try:
        with st.spinner("BirdNET is checking your recording. The first analysis may take longer while the model starts. Keep this page open."):
            with tempfile.TemporaryDirectory(prefix="vizag_bird_finder_") as temp:
                workspace = Path(temp)
                audio_path = workspace / f"recording{suffix}"
                audio_path.write_bytes(sound.getvalue())
                detections = identify_audio(
                    audio_path,
                    workspace / "birdnet_results",
                    threads=2,
                    min_confidence=float(minimum_confidence),
                    latitude=17.6868 if vizag_filter else None,
                    longitude=83.2185 if vizag_filter else None,
                )
        st.session_state["vizag_bird_result"] = {
            "detections": detections,
            "recording_name": getattr(sound, "name", "Microphone recording"),
            "minimum_confidence": float(minimum_confidence),
            "vizag_filter": vizag_filter,
        }
    except Exception as exc:
        st.error(f"We couldn't analyze this recording. {exc}")

result = st.session_state.get("vizag_bird_result")
if result:
    st.divider()
    st.header("Birds heard")
    st.caption(f"Recording: {result['recording_name']}")
    detections = result["detections"]
    if not detections:
        st.warning("I couldn't find a clear bird match in this recording. This doesn't mean there was no bird.")
        st.markdown("Try a recording with the bird louder and less background noise. In **Optional settings**, lower the minimum score or turn off **Focus on birds expected near Vizag** to search more broadly.")
    else:
        best_by_species = {}
        for detection in detections:
            name = detection["scientific_name"]
            if name not in best_by_species or detection["confidence"] > best_by_species[name]["confidence"]:
                best_by_species[name] = detection
        ranked = sorted(best_by_species.values(), key=lambda row: row["confidence"], reverse=True)
        top = ranked[0]
        st.subheader(top["common_name"] or top["scientific_name"])
        if top["common_name"]:
            st.caption(top["scientific_name"])
        st.metric("Best matching segment score", f"{top['confidence']:.2f}")
        st.caption("A higher score means a stronger model match. It is not the chance that this identification is correct.")

        if len(ranked) > 1:
            st.subheader("Other possible birds")
            st.dataframe(
                [{"Bird": row["common_name"] or row["scientific_name"],
                  "Scientific name": row["scientific_name"],
                  "Best segment score": f"{row['confidence']:.2f}"}
                 for row in ranked[1:]],
                use_container_width=True,
                hide_index=True,
            )

        st.subheader("Where they were heard")
        st.caption("Times show the audio segment where BirdNET detected each bird, when provided by the model.")
        st.dataframe(
            [{"Bird": row["common_name"] or row["scientific_name"],
              "Start time (seconds)": row.get("start_seconds"),
              "End time (seconds)": row.get("end_seconds"),
              "Score": f"{row['confidence']:.2f}"}
             for row in detections],
            use_container_width=True,
            hide_index=True,
        )

        export_rows = [{**row, "location_filter": "Visakhapatnam" if result["vizag_filter"] else None,
                        "minimum_confidence": result["minimum_confidence"]}
                       for row in detections]
        csv_file = io.StringIO(newline="")
        writer = csv.DictWriter(csv_file, fieldnames=[
            "scientific_name", "common_name", "confidence", "start_seconds", "end_seconds",
            "location_filter", "minimum_confidence",
        ])
        writer.writeheader()
        writer.writerows(export_rows)
        json_file = json.dumps({
            "recording": result["recording_name"],
            "location_filter": "Visakhapatnam" if result["vizag_filter"] else None,
            "minimum_confidence": result["minimum_confidence"],
            "detections": detections,
        }, indent=2)
        download_col1, download_col2 = st.columns(2)
        download_col1.download_button("Download results (CSV)", csv_file.getvalue(), "vizag_bird_results.csv", "text/csv", use_container_width=True)
        download_col2.download_button("Download results (JSON)", json_file, "vizag_bird_results.json", "application/json", use_container_width=True)

with st.expander("About these results"):
    st.write("Vizag Bird Finder uses BirdNET-Analyzer, an AI model that suggests bird species from sound. It can make mistakes, and location filtering may hide rare visitors. Results should be checked by listening to the recording.")
    st.markdown("BirdNET-Analyzer source code is MIT licensed; its model files are CC BY-NC-SA 4.0. Check the model terms before commercial use. [Licensing details](https://birdnet-team.github.io/BirdNET-Analyzer/stable/faq.html) · [How BirdNET analyzes sound](https://birdnet-team.github.io/BirdNET-Analyzer/stable/usage/cli.html).")
    st.caption("Uploaded audio is processed temporarily and removed after the analysis. Downloaded results remain in your browser session.")
    st.caption("App build: csv-detection-fix-3")
