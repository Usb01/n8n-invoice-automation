// n8n Code node — "Format Slack message" (mode: run once for each item)
const fmt = (n) => (n === null || n === undefined ? '–' : Number(n).toLocaleString('en-US', { minimumFractionDigits: 2 }));

const r = $json;
const head = r.status === 'ok'
  ? `:white_check_mark: Invoice logged – *${r.vendor}* #${r.invoice_number}`
  : `:warning: Invoice needs review – *${r.vendor || 'unknown vendor'}* #${r.invoice_number || '?'}`;

const lines = [
  head,
  `Total: *${r.currency || ''} ${fmt(r.total)}* (VAT ${fmt(r.vat_amount)})  ·  Due: ${r.due_date || '–'}`,
  `From: ${r.from || r.source}${r.file_name ? `  ·  File: ${r.file_name}` : ''}`,
];
if (r.issues) lines.push(`Issues: ${r.issues}`);

return { json: { ...r, slack_text: lines.join('\n') } };
