import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const record = await readFile(new URL('../record.html', import.meta.url), 'utf8');
const cook = await readFile(new URL('../cook-mode.html', import.meta.url), 'utf8');
const profile = await readFile(new URL('../profile.html', import.meta.url), 'utf8');
const landing = await readFile(new URL('../index.html', import.meta.url), 'utf8');

test('recipe review renders parser questions and requires answers before saving', () => {
  assert.match(record, /id="clarifications-list"/);
  assert.match(record, /api\.resolveParse\(latestParseResult/);
  assert.match(record, /Please answer the measure questions before saving/);
  assert.match(record, /quantity\.resolution/);
});

test('Cook Mode hides generic recipe metadata while its HTML hidden flag is set', () => {
  assert.match(cook, /recipe-meta\[hidden\]\{display:none!important\}/);
  assert.match(cook, /async function loadCookableRecipes\(\)/);
  assert.match(cook, /Choose a recipe to cook/);
});

test('profile calibration slider and numeric entry update one persisted amount field', () => {
  assert.match(profile, /id="hand-amount-slider"/);
  assert.match(profile, /id="hand-amount-number" name="amount"/);
  assert.match(profile, /handAmountSlider\?\.addEventListener\('input'/);
  assert.match(profile, /api\.addHandWeighing\(currentToken/);
});

test('landing calibration renders backend ranges and no longer claims offline cooking', () => {
  assert.match(landing, /function riceRange\(saved\)/);
  assert.match(landing, /showRange\(range,'Your saved personal range'\)/);
  assert.doesNotMatch(landing, /<\/svg>Offline<\/span>/);
  assert.match(landing, /<\/svg>Cook<\/span>/);
});
