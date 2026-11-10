import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const page = await readFile(new URL('../cook-mode.html', import.meta.url), 'utf8');

test('Cook Mode introduction has working dismiss controls instead of module-invisible inline handlers', () => {
  assert.match(page, /id="guide-touch-btn"/);
  assert.match(page, /id="guide-start-btn"/);
  assert.match(page, /id="guide-close"/);
  assert.match(page, /addEventListener\('click', closeCookGuide\)/);
  assert.match(page, /event\.key === 'Escape'/);
  assert.doesNotMatch(page, /onclick="startCook\(/);
  assert.match(page, /function closeCookGuide\(\)/);
});

test('Cook Mode does not advertise or expose a dead voice-control action', () => {
  assert.match(page, /id="voice-toggle"[^>]*disabled/);
  assert.match(page, /Voice control isn’t available yet/);
  assert.doesNotMatch(page, /toggleVoiceControls/);
});

test('Cook Mode still loads a selected recipe or offers the saved-recipe chooser', () => {
  assert.match(page, /async function loadRecipeForCooking\(\)/);
  assert.match(page, /async function loadCookableRecipes\(\)/);
  assert.match(page, /await loadRecipeForCooking\(\)/);
});
