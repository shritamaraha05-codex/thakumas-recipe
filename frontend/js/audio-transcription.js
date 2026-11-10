const TARGET_RATE = 16000;
export const MAX_AUDIO_SECONDS = 30;
const CHUNK_SECONDS = 25;
const AAC_SAMPLE_RATES = [96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350];

function parseAdtsFrames(bytes) {
  const frames = [];
  let offset = 0;
  let time = 0;
  while (offset < bytes.length) {
    if (offset + 7 > bytes.length || bytes[offset] !== 0xff || (bytes[offset + 1] & 0xf6) !== 0xf0) return null;
    const rateIndex = (bytes[offset + 2] >> 2) & 0x0f;
    const sampleRate = AAC_SAMPLE_RATES[rateIndex];
    const headerLength = (bytes[offset + 1] & 1) ? 7 : 9;
    const frameLength = ((bytes[offset + 3] & 3) << 11) | (bytes[offset + 4] << 3) | (bytes[offset + 5] >> 5);
    const duration = (1024 * ((bytes[offset + 6] & 3) + 1)) / sampleRate;
    if (!sampleRate || frameLength < headerLength || offset + frameLength > bytes.length) return null;
    frames.push({ start: offset, end: offset + frameLength, duration, startTime: time });
    offset += frameLength;
    time += duration;
  }
  return frames.length ? { frames, duration: time } : null;
}

export function splitAdtsAacIntoChunks(arrayBuffer) {
  const bytes = new Uint8Array(arrayBuffer);
  const parsed = parseAdtsFrames(bytes);
  if (!parsed) throw new Error('This AAC file is malformed or is not an ADTS AAC recording. Choose another audio file or type the narration.');
  const maxSeconds = parsed.duration <= MAX_AUDIO_SECONDS ? MAX_AUDIO_SECONDS : CHUNK_SECONDS;
  const chunks = [];
  let chunkStart = 0;
  let chunkDuration = 0;
  for (const frame of parsed.frames) {
    if (chunkDuration && chunkDuration + frame.duration > maxSeconds) {
      chunks.push(new Blob([bytes.slice(chunkStart, frame.start)], { type: 'audio/aac' }));
      chunkStart = frame.start;
      chunkDuration = 0;
    }
    chunkDuration += frame.duration;
  }
  if (chunkStart < bytes.length) chunks.push(new Blob([bytes.slice(chunkStart)], { type: 'audio/aac' }));
  return chunks;
}

export function encodePcm16Wav(samples) {
  const bytes = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(bytes);
  const writeText = (offset, value) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
  writeText(0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeText(8, 'WAVE');
  writeText(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, TARGET_RATE, true);
  view.setUint32(28, TARGET_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, 'data');
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (const sample of samples) {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += 2;
  }
  return new Blob([bytes], { type: 'audio/wav' });
}

function findLowEnergyCut(samples, start, end) {
  const frameSize = Math.round(TARGET_RATE * 0.1);
  const searchStart = Math.max(start + frameSize, end - 3 * TARGET_RATE);
  let bestStart = searchStart;
  let bestEnergy = Number.POSITIVE_INFINITY;
  for (let frameStart = searchStart; frameStart + frameSize <= end; frameStart += frameSize) {
    let energy = 0;
    for (let i = frameStart; i < frameStart + frameSize; i++) energy += samples[i] * samples[i];
    energy /= frameSize;
    if (energy < bestEnergy) { bestEnergy = energy; bestStart = frameStart; }
  }
  return Math.min(end, bestStart + frameSize);
}

export function splitMonoSamplesIntoWavChunks(samples) {
  if (samples.length <= MAX_AUDIO_SECONDS * TARGET_RATE) {
    return samples.length ? [encodePcm16Wav(samples)] : [];
  }
  const maxSamples = CHUNK_SECONDS * TARGET_RATE;
  const chunks = [];
  let start = 0;
  while (start < samples.length) {
    let end = Math.min(start + maxSamples, samples.length);
    if (end < samples.length) end = findLowEnergyCut(samples, start, end);
    if (end <= start) throw new Error('The audio could not be split into valid transcription clips.');
    chunks.push(encodePcm16Wav(samples.slice(start, end)));
    start = end;
  }
  return chunks;
}

function resampleToWavChunks(decoded) {
  if (!decoded?.length || !decoded.sampleRate || !decoded.numberOfChannels) {
    throw new Error('No playable audio was found in this file. Choose another file or type the narration.');
  }
  if (!Number.isFinite(decoded.duration) || decoded.duration <= 0) {
    throw new Error('This audio file is empty or has an invalid duration. Choose another file.');
  }
  const OfflineContextClass = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  if (!OfflineContextClass) throw new Error('This browser cannot convert audio. Try a PCM WAV file or type the narration.');
  const targetLength = Math.ceil(decoded.duration * TARGET_RATE);
  const mono = new OfflineContextClass(1, targetLength, TARGET_RATE);
  const sourceBuffer = mono.createBuffer(1, decoded.length, decoded.sampleRate);
  const mixed = sourceBuffer.getChannelData(0);
  for (let channel = 0; channel < decoded.numberOfChannels; channel++) {
    const values = decoded.getChannelData(channel);
    for (let i = 0; i < values.length; i++) mixed[i] += values[i] / decoded.numberOfChannels;
  }
  const source = mono.createBufferSource();
  source.buffer = sourceBuffer;
  source.connect(mono.destination);
  source.start();
  return mono.startRendering().then(buffer => splitMonoSamplesIntoWavChunks(buffer.getChannelData(0)));
}

async function decodeThroughMediaElement(file, AudioContextClass) {
  if (typeof document === 'undefined' || typeof AudioContextClass !== 'function') {
    throw new Error('This browser cannot decode this audio format. Try a PCM WAV file or type the narration.');
  }
  const context = new AudioContextClass();
  const audio = document.createElement('audio');
  const objectUrl = URL.createObjectURL(file);
  const chunks = [];
  let processor;
  let source;
  let silentGain;
  try {
    audio.preload = 'auto';
    await new Promise((resolve, reject) => {
      audio.addEventListener('loadedmetadata', resolve, { once: true });
      audio.addEventListener('error', () => reject(new Error('The browser cannot play this audio format. Try another audio file or type the narration.')), { once: true });
      audio.src = objectUrl;
      audio.load();
    });
    if (!Number.isFinite(audio.duration) || audio.duration <= 0) throw new Error('This file has no playable audio.');
    source = context.createMediaElementSource(audio);
    processor = context.createScriptProcessor(4096, 2, 1);
    silentGain = context.createGain();
    silentGain.gain.value = 0;
    processor.onaudioprocess = event => {
      const input = event.inputBuffer;
      const mono = new Float32Array(input.length);
      for (let channel = 0; channel < input.numberOfChannels; channel++) {
        const values = input.getChannelData(channel);
        for (let i = 0; i < input.length; i++) mono[i] += values[i] / input.numberOfChannels;
      }
      chunks.push(mono);
    };
    source.connect(processor);
    processor.connect(silentGain);
    silentGain.connect(context.destination);
    await context.resume();
    await new Promise(async (resolve, reject) => {
      audio.addEventListener('ended', resolve, { once: true });
      audio.addEventListener('error', () => reject(new Error('The browser stopped while decoding this audio. Choose another file or type the narration.')), { once: true });
      try { await audio.play(); } catch { reject(new Error('The browser could not play this audio file for conversion. Choose another file or type the narration.')); }
    });
    const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    if (!total) throw new Error('No audio samples were decoded. Choose another file or type the narration.');
    const samples = new Float32Array(total);
    let offset = 0;
    for (const chunk of chunks) { samples.set(chunk, offset); offset += chunk.length; }
    const captured = context.createBuffer(1, samples.length, context.sampleRate);
    captured.getChannelData(0).set(samples);
    return await resampleToWavChunks(captured);
  } finally {
    if (processor) { processor.onaudioprocess = null; processor.disconnect(); }
    source?.disconnect();
    silentGain?.disconnect();
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
    URL.revokeObjectURL(objectUrl);
    await context.close().catch(() => {});
  }
}

export async function audioFileToWavChunks(file) {
  const bytes = await file.arrayBuffer();
  const isAdts = bytes.byteLength >= 2 && new Uint8Array(bytes)[0] === 0xff && (new Uint8Array(bytes)[1] & 0xf6) === 0xf0;
  if (isAdts) return splitAdtsAacIntoChunks(bytes);
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) throw new Error('This browser cannot convert audio files. Try a PCM WAV file or type the narration.');
  const decoder = new AudioContextClass();
  let decoded;
  try {
    decoded = await decoder.decodeAudioData(bytes);
  } catch {
    await decoder.close().catch(() => {});
    return decodeThroughMediaElement(file, AudioContextClass);
  } finally {
    if (decoder.state !== 'closed') await decoder.close().catch(() => {});
  }
  return resampleToWavChunks(decoded);
}
