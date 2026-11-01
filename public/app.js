const form = document.querySelector('#analysis-form');
const fileInput = document.querySelector('#audio-file');
const fileLabel = document.querySelector('#file-label');
const status = document.querySelector('#status');
const results = document.querySelector('#results');
const answer = document.querySelector('#answer');
const list = document.querySelector('#detection-list');
const downloadButton = document.querySelector('#download-button');
const uploadAgain = document.querySelector('#upload-again');
const demoButtons = [...document.querySelectorAll('.demo-load')];
let currentRows = [];
let selectedDemoSpecies = '';

const setBusy = (busy) => demoButtons.forEach((demoButton) => { demoButton.disabled = busy; });
const showUpload = (visible) => { form.hidden = !visible; uploadAgain.hidden = visible; };

fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  fileLabel.textContent = file ? `${file.name} · ${(file.size / 1e6).toFixed(2)} MB` : 'Drop an audio file here or tap to choose';
  selectedDemoSpecies = '';
  if (file) form.requestSubmit();
});

uploadAgain.addEventListener('click', () => {
  showUpload(true);
  results.hidden = true;
  status.textContent = '';
  fileInput.value = '';
  fileLabel.textContent = 'Drop an audio file here or tap to choose';
  form.scrollIntoView({behavior: 'smooth', block: 'center'});
});

const dropzone = document.querySelector('.dropzone');
dropzone.addEventListener('click', (event) => { if (event.target !== fileInput) { event.preventDefault(); fileInput.click(); } });
['dragenter', 'dragover'].forEach((eventName) => dropzone.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropzone.classList.add('is-dragging');
  status.textContent = 'Release to analyze this recording.';
}));
['dragleave', 'drop'].forEach((eventName) => dropzone.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropzone.classList.remove('is-dragging');
}));
dropzone.addEventListener('drop', (event) => {
  const file = [...event.dataTransfer.files].find((candidate) => candidate.type.startsWith('audio/') || /\.(wav|mp3|flac|ogg)$/i.test(candidate.name));
  if (!file) { status.textContent = 'Drop a WAV, MP3, FLAC, or OGG audio file.'; return; }
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  fileInput.dispatchEvent(new Event('change', {bubbles: true}));
});

demoButtons.forEach((demoButton) => demoButton.addEventListener('click', async () => {
  setBusy(true);
  showUpload(false);
  results.hidden = true;
  status.textContent = 'Loading the demo recording…';
  status.scrollIntoView({behavior: 'smooth', block: 'center'});
  try {
    const response = await fetch(demoButton.dataset.demoUrl);
    if (!response.ok) throw Error('Demo audio is unavailable right now.');
    const blob = await response.blob();
    const file = new File([blob], demoButton.dataset.demoName, {type: blob.type || 'audio/ogg'});
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
    selectedDemoSpecies = demoButton.dataset.demoSpecies || '';
    form.requestSubmit();
  } catch (error) {
    status.textContent = `${error.message} You can still play it above or upload your own clip.`;
    setBusy(false);
  }
}));

const csvEscape = (value) => { const text = String(value ?? ''); return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text; };

function renderAnswer(detections, modelName) {
  answer.innerHTML = '<h3></h3><p></p>';
  const [heading, detail] = answer.children;
  if (!detections.length) {
    heading.textContent = 'No bird identified with confidence';
    detail.textContent = 'This does not mean there are no birds in the recording. Try a clearer or longer clip.';
    return;
  }
  const top = detections[0];
  const name = top.common_name || top.scientific_name;
  if (modelName === 'Verified demo reference') {
    heading.textContent = `This is a ${name}`;
    detail.textContent = `${top.scientific_name}. This name comes from the demo clip's label, not a live BirdNET analysis.`;
    return;
  }
  heading.textContent = `Most likely: ${name}`;
  detail.textContent = `${top.scientific_name} · ${Math.round(top.confidence * 100)}% BirdNET score. This is an automated suggestion, so listen and check before using it as evidence.`;
}

function renderDetections(detections) {
  list.innerHTML = '';
  if (!detections.length) { list.innerHTML = "<p class='empty'>No candidate calls reached this score. This is not evidence that the recording contains no birds.</p>"; return; }
  detections.forEach((detection) => {
    const item = document.createElement('article'); item.className = 'detection';
    const time = detection.start_seconds == null ? 'No timestamp returned' : `${detection.start_seconds.toFixed(1)}–${detection.end_seconds.toFixed(1)} s`;
    item.innerHTML = `<div><h4>${detection.common_name || detection.scientific_name}</h4><p>${detection.scientific_name}</p></div><div class="detection-meta"><strong>${Number(detection.confidence).toFixed(2)}</strong><span>${time}</span></div>`;
    list.append(item);
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault(); const file = fileInput.files[0]; if (!file) return;
  if (file.size > 3e6) { status.textContent = 'Choose a clip smaller than 3 MB.'; setBusy(false); return; }
  setBusy(true); results.hidden = true;
  status.textContent = selectedDemoSpecies ? 'Analyzing the sound…' : 'Analyzing with BirdNET. This can take a few minutes, so keep this page open.';
  status.classList.toggle('is-working', !selectedDemoSpecies);
  try {
    const bytes = new Uint8Array(await file.arrayBuffer()); let binary = ''; for (const byte of bytes) binary += String.fromCharCode(byte);
    const response = await fetch('/api/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({filename:file.name, audio_base64:btoa(binary), demo_species:selectedDemoSpecies})});
    const payload = await response.json(); if (!response.ok) throw Error(payload.error || 'Analysis could not be completed.');
    const detections = [...payload.detections].sort((a, b) => b.confidence - a.confidence);
    const recordingId = file.name.replace(/\.[^.]+$/, '');
    currentRows = detections.filter((row) => row.start_seconds != null && row.end_seconds != null).map((row) => ({recording_id:recordingId, start_seconds:row.start_seconds, end_seconds:row.end_seconds, scientific_name:row.scientific_name, confidence:row.confidence, model_name:payload.model_name}));
    renderAnswer(detections, payload.model_name); renderDetections(detections); results.hidden = false; status.textContent = '';
    results.scrollIntoView({behavior: 'smooth', block: 'center'});
  } catch (error) { status.textContent = error.message; } finally { setBusy(false); status.classList.remove('is-working'); }
});

downloadButton.addEventListener('click', () => { const fields = ['recording_id','start_seconds','end_seconds','scientific_name','confidence','model_name']; const csv = [fields.join(','), ...currentRows.map((row) => fields.map((field) => csvEscape(row[field])).join(','))].join('\n'); const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'})); link.download = 'ecosound-shift-detections.csv'; link.click(); URL.revokeObjectURL(link.href); });
