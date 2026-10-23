// n8n Code node — "Find invoices due soon" (mode: run once for all items)
// Input: every row of the Invoices sheet. Output: one item with a Slack digest, or nothing.

const DAYS_AHEAD = 3;
const today = new Date();
today.setUTCHours(0, 0, 0, 0);
const limit = new Date(today.getTime() + DAYS_AHEAD * 86400000);

const rows = $input.all().map((i) => i.json);
const open = rows.filter((r) => r.status === 'ok' && !r.paid_at && r.due_date);

const overdue = [];
const dueSoon = [];
for (const r of open) {
  const due = new Date(`${r.due_date}T00:00:00Z`);
  if (Number.isNaN(due.getTime())) continue;
  if (due < today) overdue.push(r);
  else if (due <= limit) dueSoon.push(r);
}

if (!overdue.length && !dueSoon.length) return [];

const money = (r) => `${r.currency} ${Number(r.total).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
const line = (r) => `• ${r.due_date}  ${r.vendor} #${r.invoice_number}  ${money(r)}`;
const sum = (list) => list.reduce((s, r) => s + Number(r.total || 0), 0);

const parts = [];
if (overdue.length) parts.push(`:red_circle: *Overdue (${overdue.length})* – SAR ${sum(overdue).toLocaleString('en-US')}\n${overdue.map(line).join('\n')}`);
if (dueSoon.length) parts.push(`:large_yellow_circle: *Due in the next ${DAYS_AHEAD} days (${dueSoon.length})*\n${dueSoon.map(line).join('\n')}`);

return [{ json: { slack_text: parts.join('\n\n'), overdue: overdue.length, due_soon: dueSoon.length } }];
