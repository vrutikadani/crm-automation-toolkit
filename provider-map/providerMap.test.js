// Run with: node --test provider-map/
const test = require('node:test');
const assert = require('node:assert');
const { evaluate } = require('./providerMap');

const today = new Date('2026-10-01');
const daysAgo = (n) => new Date(today.getTime() - n * 86400000).toISOString();

test('Device X owners are always listed', () => {
  const r = evaluate([{ product_line: 'device_x', amount: 90000, close_date: daysAgo(900) }], today);
  assert.equal(r.provider_map_eligible, true);
});

test('Device O with enough recent consumables is listed', () => {
  const r = evaluate([
    { product_line: 'device_o', amount: 40000, close_date: daysAgo(500) },
    { product_line: 'consumables', amount: 3000, close_date: daysAgo(30) },
    { product_line: 'consumables', amount: 2500, close_date: daysAgo(200) },
  ], today);
  assert.equal(r.consumables_net_last_365, 5500);
  assert.equal(r.provider_map_eligible, true);
});

test('old consumables outside 365 days do not count', () => {
  const r = evaluate([
    { product_line: 'device_o', amount: 40000, close_date: daysAgo(500) },
    { product_line: 'consumables', amount: 9000, close_date: daysAgo(400) },
  ], today);
  assert.equal(r.provider_map_eligible, false);
});

test('returns net out of the consumables total', () => {
  const r = evaluate([
    { product_line: 'device_o', amount: 40000, close_date: daysAgo(500) },
    { product_line: 'consumables', amount: 6000, close_date: daysAgo(10) },
    { product_line: 'consumables', amount: 1500, close_date: daysAgo(5), is_return: true },
  ], today);
  assert.equal(r.consumables_net_last_365, 4500);
  assert.equal(r.provider_map_eligible, false);
});

test('no device means not listed', () => {
  const r = evaluate([{ product_line: 'consumables', amount: 20000, close_date: daysAgo(10) }], today);
  assert.equal(r.provider_map_eligible, false);
});
