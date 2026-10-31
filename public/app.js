const form = document.querySelector('#analysis-form');
const fileInput = document.querySelector('#audio-file');
const fileLabel = document.querySelector('#file-label');
const status = document.querySelector('#status');
const results = document.querySelector('#results');
const list = document.querySelector('#detection-list');
const button = document.querySelector('#analyze-button');
const downloadButton = document.querySelector('#download-button');
let currentRows = [];
const researchMeta = () => ({site_id: document.querySelector('#site-id').value.trim(), site_type: document.querySelector('#site-type').value, hours_since_rain: document.querySelector('#hours-since-rain').value, rainfall_mm: document.querySelector('#rainfall-mm').value});

const stages = [...document.querySelectorAll('.stage')];
const recoveryFill = document.querySelector('#recovery-meter-fill');
const recoveryStatus = document.querySelector('#recovery-status');
const savedStages = new Set(JSON.parse(localStorage.getItem('ecosound-recovery-stages') || '[]'));
const updateRecovery = () => {
  stages.forEach((stage) => stage.classList.toggle('is-done', savedStages.has(stage.dataset.stage)));
  const count = savedStages.size;
  recoveryFill.style.width = `${count * 25}%`;
  recoveryStatus.textContent = `${count} of 4 sampling points complete${count === 4 ? ' · recovery series ready to export' : ''}`;
};
stages.forEach((stage) => stage.addEventListener('click', () => {
  const key = stage.dataset.stage;
  if (savedStages.has(key)) savedStages.delete(key); else savedStages.add(key);
  localStorage.setItem('ecosound-recovery-stages', JSON.stringify([...savedStages]));
  updateRecovery();
}));
updateRecovery();

fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  fileLabel.textContent = file ? `${file.name} · ${(file.size / 1e6).toFixed(2)} MB` : 'Choose a WAV, MP3, FLAC, or OGG clip';
});

const dropzone = document.querySelector('.dropzone');
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
  document.querySelector('#recording-id').value = file.name.replace(/\.[^.]+$/, '');
  form.requestSubmit();
});

document.querySelectorAll('.demo-load').forEach((demoButton) => demoButton.addEventListener('click', async () => {
  demoButton.disabled = true;
  status.textContent = 'Loading the demo recording…';
  try {
    const response = await fetch(demoButton.dataset.demoUrl);
    if (!response.ok) throw Error('Demo audio is unavailable right now.');
    const blob = await response.blob();
    const file = new File([blob], demoButton.dataset.demoName, {type: blob.type || 'audio/ogg'});
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
    fileLabel.textContent = `${file.name} · ${(file.size / 1e6).toFixed(2)} MB`;
    document.querySelector('#recording-id').value = demoButton.dataset.demoName.replace(/\.[^.]+$/, '');
    status.textContent = demoButton.dataset.autoAnalyze ? 'Demo loaded. Analyzing the sound…' : 'Demo loaded. Press Analyze recording to continue.';
    if (demoButton.dataset.autoAnalyze) form.requestSubmit();
  } catch (error) {
    status.textContent = `${error.message} You can still play it above or upload your own clip.`;
  } finally { demoButton.disabled = false; }
}));

const csvEscape = (value) => { const text = String(value ?? ''); return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text; };

function renderDetections(detections) {
  list.innerHTML = '';
  if (!detections.length) { list.innerHTML = "<p class='empty'>No candidate calls reached this score. This is not evidence that the recording contains no birds.</p>"; return; }
  detections.sort((a, b) => b.confidence - a.confidence).forEach((detection) => {
    const item = document.createElement('article'); item.className = 'detection';
    const time = detection.start_seconds == null ? 'No timestamp returned' : `${detection.start_seconds.toFixed(1)}–${detection.end_seconds.toFixed(1)} s`;
    item.innerHTML = `<div><h4>${detection.common_name || detection.scientific_name}</h4><p>${detection.scientific_name}</p></div><div class="detection-meta"><strong>${Number(detection.confidence).toFixed(2)}</strong><span>${time}</span></div>`;
    list.append(item);
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault(); const file = fileInput.files[0]; if (!file) return;
  if (file.size > 3e6) { status.textContent = 'Choose a clip smaller than 3 MB.'; return; }
  button.disabled = true; status.textContent = 'Preparing and analyzing audio…'; results.hidden = true;
  try {
    const bytes = new Uint8Array(await file.arrayBuffer()); let binary = ''; for (const byte of bytes) binary += String.fromCharCode(byte);
    const response = await fetch('/api/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({filename:file.name, audio_base64:btoa(binary), minimum_confidence:Number(document.querySelector('#minimum-confidence').value)})});
    const payload = await response.json(); if (!response.ok) throw Error(payload.error || 'Analysis could not be completed.');
    const recordingId = document.querySelector('#recording-id').value.trim() || file.name.replace(/\.[^.]+$/, '');
    currentRows = payload.detections.filter((row) => row.start_seconds != null && row.end_seconds != null).map((row) => ({...researchMeta(), recording_id:recordingId, start_seconds:row.start_seconds, end_seconds:row.end_seconds, scientific_name:row.scientific_name, confidence:row.confidence, model_name:payload.model_name}));
    renderDetections(payload.detections); results.hidden = false; status.textContent = `${payload.detections.length} candidate detection${payload.detections.length === 1 ? '' : 's'} returned. Review before using as evidence.`;
  } catch (error) { status.textContent = error.message; } finally { button.disabled = false; }
});

downloadButton.addEventListener('click', () => { const fields = ['site_id','site_type','hours_since_rain','rainfall_mm','recording_id','start_seconds','end_seconds','scientific_name','confidence','model_name']; const csv = [fields.join(','), ...currentRows.map((row) => fields.map((field) => csvEscape(row[field])).join(','))].join('\n'); const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'})); link.download = 'ecosound-shift-rain-recovery.csv'; link.click(); URL.revokeObjectURL(link.href); });
