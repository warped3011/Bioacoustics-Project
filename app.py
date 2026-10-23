"""Simple Streamlit bird sound identifier for Visakhapatnam."""

from __future__ import annotations

import csv
import io
import json
import tempfile
import zipfile
from pathlib import Path
from pathlib import PurePosixPath

import streamlit as st

from vizag_bird_finder_adapter import identify_audio
from commons_audio import search_audio
from ecosound_eval.pipeline import mfcc_features, read_manifest


FEATURED_CALLS = [
    {"name": "House Crow · Corvus splendens", "file": "House_crow,_Corvus_splendens.ogg",
     "creator": "Iamsalin", "license": "CC BY-SA 4.0",
     "source": "https://commons.wikimedia.org/wiki/File:House_crow,_Corvus_splendens.ogg",
     "license_url": "https://creativecommons.org/licenses/by-sa/4.0/"},
    {"name": "House Sparrow · Passer domesticus", "file": "House_Sparrow.ogg",
     "creator": "Gypsypkd", "license": "Public domain",
     "source": "https://commons.wikimedia.org/wiki/File:House_Sparrow.ogg",
     "license_url": "https://commons.wikimedia.org/wiki/Commons:Public_domain"},
    {"name": "Asian Koel · Eudynamys scolopaceus", "file": "Asian_Koel.ogg",
     "creator": "Philip Eapen", "license": "CC BY-SA 4.0",
     "source": "https://commons.wikimedia.org/wiki/File:Asian_Koel.ogg",
     "license_url": "https://creativecommons.org/licenses/by-sa/4.0/"},
    {"name": "Common Myna · Acridotheres tristis", "file": "CommonMynaCalls.ogg",
     "creator": "L. Shyamal", "license": "CC BY-SA 2.5",
     "source": "https://commons.wikimedia.org/wiki/File:CommonMynaCalls.ogg",
     "license_url": "https://creativecommons.org/licenses/by-sa/2.5/"},
]


st.set_page_config(page_title="Vizag Bird Finder", page_icon="🐦", layout="centered")

st.markdown(
    """
    <style>
    @media (max-width: 640px) {
        .stApp [data-testid="stAppViewContainer"] section.main > div.block-container {
            padding: 1.1rem max(1rem, env(safe-area-inset-right))
                2rem max(1rem, env(safe-area-inset-left));
        }
        .stApp h1 {
            font-size: clamp(1.8rem, 8vw, 2.5rem);
            line-height: 1.12;
            overflow-wrap: anywhere;
        }
        .stApp audio,
        .stApp [data-testid="stAudioInput"] {
            width: 100%;
            max-width: 100%;
        }
        .stApp button {
            min-height: 2.75rem;
        }
        .stApp [data-testid="stRadio"] [role="radiogroup"] {
            flex-direction: column;
            align-items: flex-start;
        }
        .stApp [data-testid="stFileUploaderDropzone"] {
            padding: 0.75rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🐦 Vizag Bird Finder")
st.write("Find likely birds in a recording from Visakhapatnam.")
st.info("Add a short bird sound below. Results are AI suggestions: please listen and verify before treating a bird as identified.")

with st.expander("Bird calls: listen and download sample recordings", expanded=False):
    st.write("Featured examples")
    for call in FEATURED_CALLS:
        with st.container(border=True):
            st.write(f"**{call['name']}**")
            audio_url = "https://commons.wikimedia.org/wiki/Special:Redirect/file/" + call["file"]
            st.audio(audio_url)
            st.markdown(f"Recorded by {call['creator']} · [{call['license']}]({call['license_url']}) · [source page]({call['source']})")
            st.link_button("Open / download original", audio_url, use_container_width=True)
    st.write("Search the Wikimedia Commons sound archive by bird name. Each result keeps its own creator credit and license; use the download link on the Commons file page.")
    st.caption("These are reference recordings, often from elsewhere in India or the species' wider range. They are not all recorded in Vizag and are not training data for this website's identifier.")
    with st.form("commons_audio_search"):
        species_query = st.text_input("Bird name", value="House Crow", placeholder="For example: Asian Koel")
        search_samples = st.form_submit_button("Find sample calls")
    if search_samples:
        try:
            with st.spinner("Searching reusable recordings…"):
                st.session_state["commons_audio_results"] = search_audio(species_query)
            st.session_state["commons_audio_query"] = species_query
        except Exception as exc:
            st.warning(f"The sound archive search is unavailable right now: {exc}")
    if "commons_audio_results" in st.session_state:
        st.caption(f"Results for {st.session_state.get('commons_audio_query', '')}")
        if not st.session_state["commons_audio_results"]:
            st.info("No matching recording with a supported reuse license was found. Try another spelling or scientific name.")
        for item in st.session_state["commons_audio_results"]:
            with st.container(border=True):
                st.write(f"**{item['title']}**")
                st.audio(item["audio_url"])
                st.markdown(f"Creator: {item['artist']} · [License: {item['license']}]({item['license_url'] or item['page_url']})")
                if item["description"]:
                    st.caption(item["description"][:500])
                left, right = st.columns(2)
                left.link_button("Download audio", item["audio_url"], use_container_width=True)
                right.link_button("Source and license", item["page_url"], use_container_width=True)
    st.markdown("[Visakhapatnam bird checklist (Avibase)](https://avibase.bsc-eoc.org/checklist.jsp?list=howardmoore&region=INseapvs) · [About licensing on Wikimedia Commons](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)")
    st.info("A sound library is not enough to train a dependable classifier. The project has no licensed, labeled training collection yet. The research pipeline can train and compare MFCC/BirdNET once the manifest contains multiple separately recorded examples per species; see the README for the exact commands.")

input_method = st.radio("How would you like to add a sound?", ["Upload a recording", "Record a sound"], horizontal=True)
if input_method == "Upload a recording":
    sound = st.file_uploader("Choose an audio file", type=["wav", "mp3", "flac", "ogg"])
else:
    sound = st.audio_input("Record a bird sound")

if sound is not None:
    st.audio(sound)

with st.expander("Train a simple local bird model from your recordings"):
    st.write("Upload a ZIP containing `manifest.csv` and the licensed recordings it lists. The MFCC model learns only from this dataset. It needs at least two species and two distinct original recordings for every species.")
    st.caption("The website currently has no bundled labeled dataset. Wikimedia Commons samples are examples to listen to; download only files whose license permits your use, keep their credits, and add them to your own manifest before training.")
    st.download_button(
        "Download blank manifest template",
        "audio_path,label,recording_id\n",
        file_name="manifest.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.download_button(
        "Download recording credits template",
        "audio_path,recording_id,common_name,scientific_name,source_page,audio_url,creator,license,license_url,recording_location,accessed_on,notes\n",
        file_name="recording_credits.csv",
        mime="text/csv",
        use_container_width=True,
    )
    training_zip = st.file_uploader("Training dataset ZIP", type=["zip"], key="training_dataset_zip")
    if st.button("Train my MFCC model", disabled=training_zip is None, use_container_width=True):
        try:
            with tempfile.TemporaryDirectory(prefix="vizag_training_") as temp_name:
                root = Path(temp_name).resolve()
                with zipfile.ZipFile(io.BytesIO(training_zip.getvalue())) as bundle:
                    members = bundle.infolist()
                    if len(members) > 1000 or sum(member.file_size for member in members) > 100_000_000:
                        raise ValueError("Keep the dataset ZIP below 100 MB uncompressed and under 1,000 files.")
                    for member in members:
                        name = member.filename.replace("\\", "/")
                        relative = PurePosixPath(name)
                        if relative.is_absolute() or ".." in relative.parts:
                            raise ValueError("The ZIP contains an unsafe file path.")
                        target = (root / Path(*relative.parts)).resolve()
                        if root not in target.parents and target != root:
                            raise ValueError("The ZIP contains an unsafe file path.")
                        if member.is_dir():
                            target.mkdir(parents=True, exist_ok=True)
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(bundle.read(member))
                manifest_path = root / "manifest.csv"
                samples = read_manifest(manifest_path)
                recordings = {}
                for item in samples:
                    recordings.setdefault(item.label, set()).add(item.recording_id)
                if len(recordings) < 2:
                    raise ValueError("Add at least two species to the training manifest.")
                insufficient = [label for label, ids in recordings.items() if len(ids) < 2]
                if insufficient:
                    raise ValueError("Each species needs at least two distinct recording_id values: " + ", ".join(insufficient))
                from sklearn.ensemble import RandomForestClassifier
                model = RandomForestClassifier(n_estimators=300, random_state=42, class_weight="balanced")
                model.fit([mfcc_features(item.audio) for item in samples], [item.label for item in samples])
                st.session_state["vizag_local_model"] = model
                st.session_state["vizag_local_model_classes"] = sorted(recordings)
                st.session_state["vizag_local_model_recordings"] = {label: len(ids) for label, ids in recordings.items()}
            st.success(f"Model trained from {len(samples)} labeled audio clips across {len(recordings)} species. This is a training count, not a measured accuracy score.")
        except Exception as exc:
            st.error(f"The training dataset could not be used: {exc}")

    if st.session_state.get("vizag_local_model") is not None:
        st.caption("Your session's learned model covers: " + ", ".join(st.session_state["vizag_local_model_classes"]))
        if sound is not None and st.button("Identify with my learned samples", use_container_width=True):
            try:
                suffix = Path(getattr(sound, "name", "recording.wav")).suffix.lower() or ".wav"
                with tempfile.TemporaryDirectory(prefix="vizag_prediction_") as temp_name:
                    audio_path = Path(temp_name) / f"recording{suffix}"
                    audio_path.write_bytes(sound.getvalue())
                    model = st.session_state["vizag_local_model"]
                    features = mfcc_features(audio_path).reshape(1, -1)
                    predicted = model.predict(features)[0]
                    scores = model.predict_proba(features)[0]
                    score = float(max(scores))
                st.success(f"Closest match from your training samples: {predicted}")
                st.caption(f"Random Forest vote fraction: {score:.2f}. This is not a calibrated probability or proof of species identity.")
            except Exception as exc:
                st.error(f"The learned model could not analyze this recording: {exc}")

with st.expander("Optional settings"):
    minimum_confidence = st.slider(
        "Minimum detection score",
        min_value=0.05,
        max_value=0.90,
        value=0.10,
        step=0.05,
        help="This starts low to show more possible birds, including quieter calls. Lower scores can add false matches; scores are not probabilities.",
    )
    vizag_filter = st.checkbox(
        "Limit results to birds expected near Vizag",
        value=False,
        help="Leave this off for a broad search. Turning it on can hide rare, seasonal, or unusual visitors.",
    )

if st.button("Find birds", type="primary", disabled=sound is None, use_container_width=True):
    st.session_state.pop("vizag_bird_result", None)
    suffix = Path(getattr(sound, "name", "recording.wav")).suffix.lower() or ".wav"
    if suffix not in {".wav", ".mp3", ".flac", ".ogg"}:
        suffix = ".wav"
    try:
        with st.spinner("BirdNET is checking your recording. The first run may take longer to prepare its model. Keep this page open."):
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
        st.markdown("Try a closer, clearer recording with less wind or traffic. In **Optional settings**, lower the minimum score or, if enabled, turn off **Limit results to birds expected near Vizag**.")
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
            for row in ranked[1:]:
                with st.container(border=True):
                    st.write(f"**{row['common_name'] or row['scientific_name']}**")
                    if row["common_name"]:
                        st.caption(row["scientific_name"])
                    st.caption(f"Best segment score: {row['confidence']:.2f}")

        st.subheader("Where they were heard")
        st.caption("Times show the audio segment where BirdNET detected each bird, when provided by the model.")
        for row in detections:
            with st.container(border=True):
                st.write(f"**{row['common_name'] or row['scientific_name']}**")
                if row["common_name"]:
                    st.caption(row["scientific_name"])
                start = row.get("start_seconds")
                end = row.get("end_seconds")
                if start is not None and end is not None:
                    st.caption(f"Heard from {start:.1f} to {end:.1f} seconds · Score {row['confidence']:.2f}")
                else:
                    st.caption(f"Score {row['confidence']:.2f}")

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
        st.download_button("Download results (CSV)", csv_file.getvalue(), "vizag_bird_results.csv", "text/csv", use_container_width=True)
        st.download_button("Download results (JSON)", json_file, "vizag_bird_results.json", "application/json", use_container_width=True)

with st.expander("About these results"):
    st.write("Vizag Bird Finder uses BirdNET-Analyzer, an AI model that suggests bird species from sound. It can make mistakes, and location filtering may hide rare visitors. Results should be checked by listening to the recording.")
    st.markdown("BirdNET-Analyzer source code is MIT licensed; its model files are CC BY-NC-SA 4.0. Check the model terms before commercial use. [Licensing details](https://birdnet-team.github.io/BirdNET-Analyzer/stable/faq.html) · [How BirdNET analyzes sound](https://birdnet-team.github.io/BirdNET-Analyzer/stable/usage/cli.html).")
    st.caption("Uploaded audio is processed temporarily and removed after the analysis. Downloaded results remain in your browser session.")
    st.caption("App build: corpus-intake-templates-1")
