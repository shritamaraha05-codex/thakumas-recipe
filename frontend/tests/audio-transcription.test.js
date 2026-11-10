import test from 'node:test';
import assert from 'node:assert/strict';
import { splitMonoSamplesIntoWavChunks } from '../js/audio-transcription.js';

function readWavChunk(blob) {
  return blob.arrayBuffer().then(buffer => {
    const view = new DataView(buffer);
    return {
      format: String.fromCharCode(...new Uint8Array(buffer, 0, 4)),
      sampleRate: view.getUint32(24, true),
      channels: view.getUint16(22, true),
      bits: view.getUint16(34, true),
      seconds: view.getUint32(40, true) / (view.getUint32(24, true) * view.getUint16(22, true) * (view.getUint16(34, true) / 8)),
    };
  });
}

test('sends a short recording as one mono 16 kHz PCM16 WAV', async () => {
  const samples = new Float32Array(12 * 16000).fill(0.15);
  const chunks = splitMonoSamplesIntoWavChunks(samples);
  assert.equal(chunks.length, 1);
  assert.equal(chunks[0].type, 'audio/wav');
  assert.deepEqual(await readWavChunk(chunks[0]), { format: 'RIFF', sampleRate: 16000, channels: 1, bits: 16, seconds: 12 });
});

test('keeps clips up to Gnani REST limit in one request', async () => {
  const chunks = splitMonoSamplesIntoWavChunks(new Float32Array(28 * 16000).fill(0.1));
  assert.equal(chunks.length, 1);
  assert.equal((await readWavChunk(chunks[0])).seconds, 28);
});

test('splits a long recording sequentially at quiet frames with each REST clip under 30 seconds', async () => {
  const samples = new Float32Array(60 * 16000).fill(0.2);
  samples.fill(0, 23 * 16000, 23.2 * 16000);
  samples.fill(0, 48 * 16000, 48.2 * 16000);
  const chunks = splitMonoSamplesIntoWavChunks(samples);
  assert.equal(chunks.length, 3);
  const headers = await Promise.all(chunks.map(readWavChunk));
  assert.ok(headers.every(header => header.seconds <= 25 && header.sampleRate === 16000 && header.channels === 1 && header.bits === 16));
  assert.ok(headers[0].seconds >= 23 && headers[0].seconds <= 23.2);
});
