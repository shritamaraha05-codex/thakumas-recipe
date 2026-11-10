import test from 'node:test';
import assert from 'node:assert/strict';
import { findLowEnergyCut, splitMonoSamplesIntoWavChunks } from '../js/audio-transcription.js';

test('finds a quiet cut in the final three seconds of the 25-second window', () => {
  const samples = new Float32Array(25 * 16000).fill(0.5);
  samples.fill(0, 23 * 16000, 23.2 * 16000);
  const cut = findLowEnergyCut(samples, 0, samples.length);
  assert.ok(cut >= 22 * 16000);
  assert.ok(cut <= 25 * 16000);
  assert.ok(cut >= 23 * 16000 && cut <= 23.2 * 16000);
});

test('keeps a chunk cut at or before the supplied end', () => {
  const samples = new Float32Array(25 * 16000).fill(0.2);
  assert.ok(findLowEnergyCut(samples, 0, samples.length) <= samples.length);
});

test('converts a 60-second mono stream into sequential WAV chunks no longer than 25 seconds', () => {
  const samples = new Float32Array(60 * 16000).fill(0.15);
  samples.fill(0, 23 * 16000, 23.2 * 16000);
  samples.fill(0, 48 * 16000, 48.2 * 16000);
  const chunks = splitMonoSamplesIntoWavChunks(samples);
  assert.equal(chunks.length, 3);
  for (const chunk of chunks) {
    assert.equal(chunk.type, 'audio/wav');
    assert.ok((chunk.size - 44) / (16000 * 2) <= 25);
  }
});
