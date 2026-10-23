// n8n Code node — "Validate invoice" (mode: run once for each item)
// Input:  OpenAI chat completion response ($json.choices[0].message.content)
//         + meta from "Build extraction request"
// Output: one flat row ready for Google Sheets, with status "ok" or "review" and the reasons.

const VAT_RATE = 0.15;          // KSA standard rate
const TOLERANCE = 0.05;         // rounding differences on totals, in currency units
const MIN_CONFIDENCE = 0.7;

const meta = $('Build extraction request').item.json.meta;

let data;
try {
  data = JSON.parse($json.choices[0].message.content);
} catch (e) {
  return { json: { ...emptyRow(meta), status: 'review', issues: 'model did not return valid JSON' } };
}

const num = (v) => {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(String(v).replace(/[^0-9.-]/g, ''));
  return Number.isFinite(n) ? Math.round(n * 100) / 100 : null;
};

const isoDate = (v) => {
  if (!v) return null;
  const s = String(v).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const m = s.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/); // dd/mm/yyyy
  if (m) return `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
  return null;
};

const subtotal = num(data.subtotal);
const vat = num(data.vat_amount);
const total = num(data.total);
const currency = (data.currency || 'SAR').toUpperCase();
const issues = [];

if (!data.vendor_name) issues.push('missing vendor');
if (!data.invoice_number) issues.push('missing invoice number');
if (total === null) issues.push('missing total');

const invoiceDate = isoDate(data.invoice_date);
const dueDate = isoDate(data.due_date);
if (!invoiceDate) issues.push('invoice date unreadable');
if (invoiceDate && dueDate && dueDate < invoiceDate) issues.push('due date before invoice date');

if (subtotal !== null && vat !== null && total !== null && Math.abs(subtotal + vat - total) > TOLERANCE) {
  issues.push(`subtotal + VAT (${(subtotal + vat).toFixed(2)}) ≠ total (${total.toFixed(2)})`);
}
if (currency === 'SAR' && subtotal !== null && vat !== null && Math.abs(subtotal * VAT_RATE - vat) > Math.max(TOLERANCE, subtotal * 0.002)) {
  issues.push(`VAT is not 15% of subtotal`);
}

const vatNo = data.vendor_vat_number ? String(data.vendor_vat_number).replace(/\s/g, '') : null;
if (currency === 'SAR' && vatNo && !/^3\d{13}3$/.test(vatNo)) issues.push('vendor VAT number format looks wrong');

const items = Array.isArray(data.line_items) ? data.line_items : [];
const itemsSum = items.reduce((s, it) => s + (num(it.amount) || 0), 0);
if (items.length && subtotal !== null && Math.abs(itemsSum - subtotal) > TOLERANCE) {
  issues.push(`line items add up to ${itemsSum.toFixed(2)}, subtotal says ${subtotal.toFixed(2)}`);
}

const confidence = num(data.confidence);
if (confidence !== null && confidence < MIN_CONFIDENCE) issues.push(`low extraction confidence (${confidence})`);

const vendor = (data.vendor_name || '').trim();
return {
  json: {
    key: `${vendor.toLowerCase().replace(/[^a-z0-9]/g, '')}|${String(data.invoice_number || '').trim()}`,
    status: issues.length ? 'review' : 'ok',
    issues: issues.join('; '),
    vendor,
    vendor_vat_number: vatNo,
    invoice_number: data.invoice_number || null,
    invoice_date: invoiceDate,
    due_date: dueDate,
    currency,
    subtotal,
    vat_amount: vat,
    total,
    line_items: items.length,
    source: meta.source,
    from: meta.from,
    file_name: meta.file_name,
    received_at: meta.received_at,
  },
};

function emptyRow(m) {
  return { key: null, vendor: null, invoice_number: null, total: null, source: m.source, from: m.from,
           file_name: m.file_name, received_at: m.received_at };
}
