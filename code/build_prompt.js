// n8n Code node — "Build extraction request" (mode: run once for each item)
// Input:  $json.text  (from Extract From File), $json.source / $json.from (where it came from)
// Output: { request, meta } – request is posted as-is to the OpenAI chat completions API.

const MAX_CHARS = 12000; // invoices are short; this keeps token cost predictable

const text = String($json.text || '').replace(/\s+\n/g, '\n').trim().slice(0, MAX_CHARS);

const system = [
  'You extract data from supplier invoices for an accounts payable team in Saudi Arabia.',
  'Return ONLY a JSON object with these keys:',
  'vendor_name, vendor_vat_number, invoice_number, invoice_date (YYYY-MM-DD), due_date (YYYY-MM-DD or null),',
  'currency (ISO code), subtotal, vat_amount, total (numbers, no thousands separators),',
  'line_items (array of {description, quantity, unit_price, amount}), confidence (0-1).',
  'Use null for anything not present. Never guess a VAT number or invoice number.',
].join(' ');

return {
  json: {
    request: {
      model: 'gpt-4o-mini',
      temperature: 0,
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: `Invoice text:\n"""\n${text}\n"""` },
      ],
    },
    meta: {
      source: $json.source || 'email',
      from: $json.from || null,
      file_name: $json.file_name || null,
      received_at: new Date().toISOString(),
      text_length: text.length,
    },
  },
};
