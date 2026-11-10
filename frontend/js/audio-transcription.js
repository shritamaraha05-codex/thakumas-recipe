const TARGET_RATE = 16000;
const MAX_CHUNK_SECONDS = 25;

export function findLowEnergyCut(samples, start, end) {
  const frameSize = Math.round(TARGET_RATE * 0.1);
  const searchStart = Math.max(start + frameSize, end - 3 * TARGET_RATE);
  let bestStart = searchStart;
  let bestEnergy = Number.POSITIVE_INFINITY;
  for (let frameStart = searchStart; frameStart + frameSize <= end; frameStart += frameSize) {
    let energy = 0;
    for (let i = frameStart; i < frameStart + frameSize; i++) energy += samples[i] * samples[i];
    energy /= frameSize;
    if (energy < bestEnergy) {
      bestEnergy = energy;
      bestStart = frameStart;
    }
  }
  return bestStart + frameSize;
}

function encodePcm16Wav(samples) {
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

export function splitMonoSamplesIntoWavChunks(samples) {
  const maxSamples = MAX_CHUNK_SECONDS * TARGET_RATE;
  const chunks = [];
  let start = 0;
  while (start < samples.length) {
    let end = Math.min(start + maxSamples, samples.length);
    if (end < samples.length) end = findLowEnergyCut(samples, start, end);
    if (end <= start) throw new Error('The audio could not be split into valid chunks.');
    chunks.push(encodePcm16Wav(samples.slice(start, end)));
    start = end;
  }
  return chunks;
}

export async function audioFileToWavChunks(file) {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  const OfflineContextClass = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  if (!AudioContextClass || !OfflineContextClass) throw new Error('This browser cannot decode audio files. Try a WAV file or type the narration.');
  const decoder = new AudioContextClass();
  let decoded;
  try {
    decoded = await decoder.decodeAudioData(await file.arrayBuffer());
  } finally {
    await decoder.close().catch(() => {});
  }

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
  const resampled = (await mono.startRendering()).getChannelData(0);
  return splitMonoSamplesIntoWavChunks(resampled);
}
