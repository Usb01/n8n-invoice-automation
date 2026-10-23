"""Generate the n8n workflow JSON files from the JS in code/.

Keeping the Code node logic in real .js files means it can be linted and unit
tested (tests/*.test.js) instead of living inside a JSON string. Run this after
editing anything in code/:

    python scripts/build_workflows.py
"""
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "code"
OUT = ROOT / "workflows"

SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"
SLACK_CHANNEL = "#finance-invoices"


def nid(name: str) -> str:
    # stable ids so regenerating doesn't produce a noisy diff
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"n8n-invoice-automation/{name}"))


def node(name, type_, version, pos, params, **extra):
    n = {"parameters": params, "id": nid(name), "name": name, "type": type_, "typeVersion": version, "position": pos}
    n.update(extra)
    return n


def code_node(name, file, pos, mode="runOnceForEachItem"):
    params = {"jsCode": (CODE / file).read_text().strip() + "\n"}
    if mode != "runOnceForAllItems":
        params = {"mode": mode, **params}
    return node(name, "n8n-nodes-base.code", 2, pos, params)


def sheet_rl(tab):
    return {
        "documentId": {"__rl": True, "value": SHEET_URL, "mode": "url"},
        "sheetName": {"__rl": True, "value": tab, "mode": "name"},
    }


def slack(name, pos, text="={{ $json.slack_text }}"):
    return node(name, "n8n-nodes-base.slack", 2.3, pos, {
        "select": "channel",
        "channelId": {"__rl": True, "value": SLACK_CHANNEL, "mode": "name"},
        "text": text,
        "otherOptions": {"includeLinkToWorkflow": False},
    })


def connect(*pairs):
    """connect(("A", "B"), ("IF", "X", 0), ("IF", "Y", 1))"""
    out = {}
    for pair in pairs:
        src, dst, idx = (*pair, 0) if len(pair) == 2 else pair
        outputs = out.setdefault(src, {"main": []})["main"]
        while len(outputs) <= idx:
            outputs.append([])
        outputs[idx].append({"node": dst, "type": "main", "index": 0})
    return out


def workflow(name, nodes, connections, tags):
    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1", "saveManualExecutions": True, "timezone": "Asia/Riyadh"},
        "tags": [{"name": t} for t in tags],
        "meta": {"templateCredsSetupCompleted": False},
        "pinData": {},
    }


def invoice_intake():
    nodes = [
        node("Gmail Trigger", "n8n-nodes-base.gmailTrigger", 1.2, [0, 0], {
            "pollTimes": {"item": [{"mode": "everyX", "value": 5, "unit": "minutes"}]},
            "simple": False,
            "filters": {"q": "has:attachment filename:pdf -label:invoice-processed (invoice OR فاتورة)"},
            "options": {"downloadAttachments": True, "dataPropertyAttachmentsPrefixName": "attachment_"},
        }),
        node("Upload webhook", "n8n-nodes-base.webhook", 2, [0, 220], {
            "httpMethod": "POST",
            "path": "invoice-upload",
            "responseMode": "onReceived",
            "options": {"binaryPropertyName": "file"},
        }, webhookId=nid("webhook-id")),
        node("Tag email", "n8n-nodes-base.set", 3.4, [220, 0], {
            "assignments": {"assignments": [
                {"id": nid("a1"), "name": "source", "value": "email", "type": "string"},
                {"id": nid("a2"), "name": "from", "value": "={{ $json.from?.value?.[0]?.address || $json.from?.text }}", "type": "string"},
                {"id": nid("a3"), "name": "file_name", "value": "={{ $binary.attachment_0?.fileName }}", "type": "string"},
            ]},
            "includeOtherFields": False,
            "options": {"stripBinary": False},
        }),
        node("Tag upload", "n8n-nodes-base.set", 3.4, [220, 220], {
            "assignments": {"assignments": [
                {"id": nid("b1"), "name": "source", "value": "upload", "type": "string"},
                {"id": nid("b2"), "name": "from", "value": "={{ $json.body?.uploaded_by || 'webhook' }}", "type": "string"},
                {"id": nid("b3"), "name": "file_name", "value": "={{ Object.values($binary)[0]?.fileName }}", "type": "string"},
            ]},
            "includeOtherFields": False,
            "options": {"stripBinary": False},
        }),
        node("Extract PDF text", "n8n-nodes-base.extractFromFile", 1, [440, 110], {
            "operation": "pdf",
            "binaryPropertyName": "={{ Object.keys($binary)[0] }}",
            "options": {"keepSource": "json", "joinPages": True},
        }),
        code_node("Build extraction request", "build_prompt.js", [660, 110]),
        node("OpenAI – extract fields", "n8n-nodes-base.httpRequest", 4.2, [880, 110], {
            "method": "POST",
            "url": "https://api.openai.com/v1/chat/completions",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "openAiApi",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json.request) }}",
            "options": {"timeout": 60000},
        }, retryOnFail=True, maxTries=3, waitBetweenTries=3000),
        code_node("Validate invoice", "validate_invoice.js", [1100, 110]),
        node("Skip already processed", "n8n-nodes-base.removeDuplicates", 2, [1320, 110], {
            "operation": "removeItemsSeenInPreviousExecutions",
            "dedupeValue": "={{ $json.key || $json.received_at }}",
            "options": {},
        }),
        node("Passed checks?", "n8n-nodes-base.if", 2.2, [1540, 110], {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                "conditions": [{
                    "id": nid("cond-status"),
                    "leftValue": "={{ $json.status }}",
                    "rightValue": "ok",
                    "operator": {"type": "string", "operation": "equals"},
                }],
                "combinator": "and",
            },
            "options": {},
        }),
        node("Sheet: Invoices", "n8n-nodes-base.googleSheets", 4.5, [1760, 0], {
            "operation": "appendOrUpdate",
            **sheet_rl("Invoices"),
            "columns": {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": ["key"], "schema": []},
            "options": {},
        }),
        node("Sheet: Needs review", "n8n-nodes-base.googleSheets", 4.5, [1760, 220], {
            "operation": "append",
            **sheet_rl("Needs review"),
            "columns": {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []},
            "options": {},
        }),
        code_node("Format Slack message", "format_slack.js", [1980, 110]),
        slack("Notify finance", [2200, 110]),
        node("Sticky: how it works", "n8n-nodes-base.stickyNote", 1, [-40, -260], {
            "content": "## Invoice intake\nPDF invoices arrive by **email** (Gmail label filter) or **upload** "
                       "(POST multipart to /webhook/invoice-upload).\n\nOpenAI extracts the fields → a Code node checks "
                       "totals, 15% VAT, VAT number format and dates → clean invoices go to **Invoices**, anything "
                       "suspicious goes to **Needs review**. Finance gets a Slack message either way.",
            "height": 220, "width": 520,
        }),
    ]
    conns = connect(
        ("Gmail Trigger", "Tag email"), ("Upload webhook", "Tag upload"),
        ("Tag email", "Extract PDF text"), ("Tag upload", "Extract PDF text"),
        ("Extract PDF text", "Build extraction request"), ("Build extraction request", "OpenAI – extract fields"),
        ("OpenAI – extract fields", "Validate invoice"), ("Validate invoice", "Skip already processed"),
        ("Skip already processed", "Passed checks?"),
        ("Passed checks?", "Sheet: Invoices", 0), ("Passed checks?", "Sheet: Needs review", 1),
        ("Sheet: Invoices", "Format Slack message"), ("Sheet: Needs review", "Format Slack message"),
        ("Format Slack message", "Notify finance"),
    )
    return workflow("Invoice intake – email/upload → AI extraction → Sheets + Slack", nodes, conns,
                    ["finance", "ai", "invoices"])


def due_soon():
    nodes = [
        node("Every weekday 8:00", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 0], {
            "rule": {"interval": [{"field": "cronExpression", "expression": "0 8 * * 0-4"}]},
        }),
        node("Read Invoices sheet", "n8n-nodes-base.googleSheets", 4.5, [220, 0], {
            "operation": "read",
            **sheet_rl("Invoices"),
            "options": {},
        }),
        code_node("Find invoices due soon", "due_soon_digest.js", [440, 0], mode="runOnceForAllItems"),
        slack("Post digest", [660, 0]),
    ]
    conns = connect(("Every weekday 8:00", "Read Invoices sheet"), ("Read Invoices sheet", "Find invoices due soon"),
                    ("Find invoices due soon", "Post digest"))
    return workflow("Invoices due soon – daily Slack digest", nodes, conns, ["finance", "invoices"])


def error_handler():
    nodes = [
        node("Error Trigger", "n8n-nodes-base.errorTrigger", 1, [0, 0], {}),
        slack("Alert #automation-alerts", [220, 0],
              text="=:rotating_light: *{{ $json.workflow.name }}* failed at node *{{ $json.execution.lastNodeExecuted }}*\n"
                   "{{ $json.execution.error.message }}\n<{{ $json.execution.url }}|Open execution>"),
    ]
    nodes[1]["parameters"]["channelId"]["value"] = "#automation-alerts"
    return workflow("Error handler – Slack alert", nodes, connect(("Error Trigger", "Alert #automation-alerts")),
                    ["ops"])


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for fname, wf in [("invoice-intake.json", invoice_intake()), ("invoices-due-soon.json", due_soon()),
                      ("error-handler.json", error_handler())]:
        (OUT / fname).write_text(json.dumps(wf, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", fname, f"({len(wf['nodes'])} nodes)")
