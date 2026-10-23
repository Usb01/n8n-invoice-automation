const test = require('node:test');
const assert = require('node:assert/strict');
const { runCodeNode } = require('./harness');
const samples = require('../samples/extractions.json');

const meta = { source: 'email', from: 'ap@vendor.sa', file_name: 'inv.pdf', received_at: '2026-10-20T08:00:00Z' };
const completion = (obj) => ({ choices: [{ message: { content: typeof obj === 'string' ? obj : JSON.stringify(obj) } }] });
const validate = (obj) =>
  runCodeNode('validate_invoice.js', { json: completion(obj), nodes: { 'Build extraction request': { meta } } }).json;

test('clean KSA invoice passes', () => {
  const r = validate(samples.clean);
  assert.equal(r.status, 'ok', r.issues);
  assert.equal(r.total, 11500);
  assert.equal(r.key, 'gulftechsupplies|INV-2026-0412');
});

test('VAT that is not 15% is flagged', () => {
  const r = validate({ ...samples.clean, vat_amount: 1000, total: 11000 });
  assert.equal(r.status, 'review');
  assert.match(r.issues, /VAT is not 15%/);
});

test('totals that do not add up are flagged', () => {
  const r = validate({ ...samples.clean, total: 12000 });
  assert.match(r.issues, /≠ total/);
});

test('line items must match subtotal', () => {
  const r = validate(samples.line_item_mismatch);
  assert.match(r.issues, /line items add up to/);
});

test('dd/mm/yyyy dates are normalised', () => {
  const r = validate({ ...samples.clean, invoice_date: '05/10/2026', due_date: '04/11/2026' });
  assert.equal(r.invoice_date, '2026-10-05');
  assert.equal(r.due_date, '2026-11-04');
  assert.equal(r.status, 'ok');
});

test('bad VAT number and missing invoice number', () => {
  const r = validate({ ...samples.clean, vendor_vat_number: '12345', invoice_number: null });
  assert.match(r.issues, /missing invoice number/);
  assert.match(r.issues, /VAT number format/);
});

test('amounts written as strings with separators', () => {
  const r = validate({ ...samples.clean, subtotal: '10,000.00', vat_amount: 'SAR 1,500', total: '11,500.00' });
  assert.equal(r.status, 'ok', r.issues);
});

test('non-JSON model output goes to review', () => {
  const r = validate('Sorry, I cannot read this invoice.');
  assert.equal(r.status, 'review');
  assert.match(r.issues, /valid JSON/);
});

test('foreign currency skips KSA VAT checks', () => {
  const r = validate(samples.usd);
  assert.equal(r.status, 'ok', r.issues);
});

test('low confidence is flagged', () => {
  const r = validate({ ...samples.clean, confidence: 0.4 });
  assert.match(r.issues, /low extraction confidence/);
});

test('prompt builder trims long text and keeps meta', () => {
  const out = runCodeNode('build_prompt.js', { json: { text: 'x'.repeat(20000), source: 'upload', file_name: 'a.pdf' } }).json;
  assert.equal(out.meta.text_length, 12000);
  assert.equal(out.meta.source, 'upload');
  assert.equal(out.request.response_format.type, 'json_object');
});

test('slack message shows issues for review items', () => {
  const out = runCodeNode('format_slack.js', { json: { status: 'review', vendor: 'X', invoice_number: '1', total: 10,
    vat_amount: 1, currency: 'SAR', issues: 'missing total' } }).json;
  assert.match(out.slack_text, /needs review/);
  assert.match(out.slack_text, /Issues: missing total/);
});

test('due soon digest groups overdue and upcoming, ignores paid', () => {
  const day = (n) => new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);
  const rows = [
    { status: 'ok', vendor: 'A', invoice_number: '1', currency: 'SAR', total: 100, due_date: day(-2) },
    { status: 'ok', vendor: 'B', invoice_number: '2', currency: 'SAR', total: 200, due_date: day(1) },
    { status: 'ok', vendor: 'C', invoice_number: '3', currency: 'SAR', total: 300, due_date: day(10) },
    { status: 'ok', vendor: 'D', invoice_number: '4', currency: 'SAR', total: 400, due_date: day(-1), paid_at: '2026-10-01' },
  ];
  const [out] = runCodeNode('due_soon_digest.js', { items: rows });
  assert.equal(out.json.overdue, 1);
  assert.equal(out.json.due_soon, 1);
  assert.doesNotMatch(out.json.slack_text, /#3|#4/);
});

test('digest returns nothing when all is quiet', () => {
  assert.deepEqual(runCodeNode('due_soon_digest.js', { items: [] }), []);
});
