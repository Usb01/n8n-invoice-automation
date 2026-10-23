"""Draw a workflow JSON as an SVG (docs/<name>.svg) for the README.

It uses node positions from the export, so the picture matches the n8n
canvas layout. Run: python scripts/render_diagram.py workflows/invoice-intake.json
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOX = 76
COLORS = {
    "gmailTrigger": "#ea4335", "webhook": "#6b7280", "scheduleTrigger": "#0ea5e9", "errorTrigger": "#dc2626",
    "set": "#2563eb", "extractFromFile": "#7c3aed", "code": "#f59e0b", "httpRequest": "#10a37f",
    "removeDuplicates": "#0891b2", "if": "#16a34a", "googleSheets": "#0f9d58", "slack": "#611f69",
}
LABEL = {
    "gmailTrigger": "Gmail", "webhook": "Webhook", "scheduleTrigger": "Schedule", "errorTrigger": "Error",
    "set": "Set", "extractFromFile": "PDF", "code": "JS", "httpRequest": "OpenAI", "removeDuplicates": "Dedupe",
    "if": "IF", "googleSheets": "Sheets", "slack": "Slack",
}


def render(wf_path: Path) -> Path:
    wf = json.loads(wf_path.read_text())
    nodes = [n for n in wf["nodes"] if not n["type"].endswith("stickyNote")]
    pos = {n["name"]: n["position"] for n in nodes}
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    ox, oy = min(xs) - 60, min(ys) - 50
    w, h = max(xs) - ox + BOX + 90, max(ys) - oy + BOX + 90

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
             f'font-family="Inter, Segoe UI, Arial, sans-serif">',
             f'<rect width="{w}" height="{h}" fill="#f4f4f6"/>',
             '<defs><pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse">'
             '<circle cx="1" cy="1" r="1" fill="#d4d4d8"/></pattern></defs>',
             f'<rect width="{w}" height="{h}" fill="url(#dots)"/>']

    for src, conn in wf["connections"].items():
        for out_idx, outs in enumerate(conn["main"]):
            for c in outs:
                x1, y1 = pos[src][0] - ox + BOX, pos[src][1] - oy + BOX / 2
                if len(conn["main"]) > 1:
                    y1 += (out_idx - (len(conn["main"]) - 1) / 2) * 22
                x2, y2 = pos[c["node"]][0] - ox, pos[c["node"]][1] - oy + BOX / 2
                mx = (x1 + x2) / 2
                parts.append(f'<path d="M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}" fill="none" stroke="#9ca3af" stroke-width="2"/>')
                parts.append(f'<circle cx="{x2}" cy="{y2}" r="4" fill="#9ca3af"/>')
                if len(conn["main"]) > 1:
                    tag = "true" if out_idx == 0 else "false"
                    parts.append(f'<text x="{x1 + 8}" y="{y1 - 5}" font-size="11" fill="#6b7280">{tag}</text>')

    for n in nodes:
        kind = n["type"].split(".")[-1]
        x, y = n["position"][0] - ox, n["position"][1] - oy
        color = COLORS.get(kind, "#6b7280")
        trigger = kind.endswith("Trigger") or kind == "webhook"
        rx = 'rx="10"'
        if trigger:
            parts.append(f'<path d="M{x + 30},{y} H{x + BOX - 10} Q{x + BOX},{y} {x + BOX},{y + 10} V{y + BOX - 10} '
                         f'Q{x + BOX},{y + BOX} {x + BOX - 10},{y + BOX} H{x + 30} A30,38 0 0 1 {x + 30},{y} Z" '
                         f'fill="#fff" stroke="{color}" stroke-width="2"/>')
        else:
            parts.append(f'<rect x="{x}" y="{y}" width="{BOX}" height="{BOX}" {rx} fill="#fff" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x + BOX / 2}" y="{y + BOX / 2 + 5}" text-anchor="middle" font-size="14" '
                     f'font-weight="700" fill="{color}">{LABEL.get(kind, kind)}</text>')
        for i, line in enumerate(_wrap(n["name"], 18)):
            parts.append(f'<text x="{x + BOX / 2}" y="{y + BOX + 18 + i * 15}" text-anchor="middle" font-size="12.5" '
                         f'fill="#111827">{html.escape(line)}</text>')

    parts.append("</svg>")
    out = ROOT / "docs" / (wf_path.stem + ".svg")
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(parts))
    return out


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for wd in words:
        if cur and len(cur) + len(wd) + 1 > width:
            lines.append(cur)
            cur = wd
        else:
            cur = f"{cur} {wd}".strip()
    return lines + [cur] if cur else lines


if __name__ == "__main__":
    for p in sys.argv[1:] or sorted((ROOT / "workflows").glob("*.json")):
        print("wrote", render(Path(p)))
