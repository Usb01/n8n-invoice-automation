// Structural checks on the exported workflow JSON, so a broken export never gets committed.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const DIR = path.join(__dirname, '..', 'workflows');
const CODE = path.join(__dirname, '..', 'code');

// node type -> typeVersions this repo is allowed to use (checked against n8n-nodes-base 2.x definitions)
const KNOWN = {
  'n8n-nodes-base.gmailTrigger': [1.2], 'n8n-nodes-base.webhook': [2], 'n8n-nodes-base.set': [3.4],
  'n8n-nodes-base.extractFromFile': [1], 'n8n-nodes-base.code': [2], 'n8n-nodes-base.httpRequest': [4.2],
  'n8n-nodes-base.removeDuplicates': [2], 'n8n-nodes-base.if': [2.2], 'n8n-nodes-base.googleSheets': [4.5],
  'n8n-nodes-base.slack': [2.3], 'n8n-nodes-base.stickyNote': [1], 'n8n-nodes-base.scheduleTrigger': [1.2],
  'n8n-nodes-base.errorTrigger': [1],
};

const files = fs.readdirSync(DIR).filter((f) => f.endsWith('.json'));

for (const file of files) {
  const wf = JSON.parse(fs.readFileSync(path.join(DIR, file), 'utf8'));

  test(`${file}: nodes are known types and versions`, () => {
    for (const n of wf.nodes) {
      assert.ok(KNOWN[n.type], `${n.name}: unknown type ${n.type}`);
      assert.ok(KNOWN[n.type].includes(n.typeVersion), `${n.name}: version ${n.typeVersion}`);
    }
  });

  test(`${file}: names and ids are unique`, () => {
    const names = wf.nodes.map((n) => n.name);
    const ids = wf.nodes.map((n) => n.id);
    assert.equal(new Set(names).size, names.length);
    assert.equal(new Set(ids).size, ids.length);
  });

  test(`${file}: every connection points at a real node and every node is wired`, () => {
    const names = new Set(wf.nodes.map((n) => n.name));
    const touched = new Set();
    for (const [src, { main }] of Object.entries(wf.connections)) {
      assert.ok(names.has(src), `connection from missing node ${src}`);
      touched.add(src);
      for (const out of main) for (const c of out) {
        assert.ok(names.has(c.node), `${src} -> missing node ${c.node}`);
        touched.add(c.node);
      }
    }
    for (const n of wf.nodes) {
      if (n.type !== 'n8n-nodes-base.stickyNote') assert.ok(touched.has(n.name), `${n.name} is not connected`);
    }
  });

  test(`${file}: Code nodes match code/*.js (run scripts/build_workflows.py)`, () => {
    const sources = Object.fromEntries(fs.readdirSync(CODE).map((f) => [fs.readFileSync(path.join(CODE, f), 'utf8').trim(), f]));
    for (const n of wf.nodes.filter((x) => x.type === 'n8n-nodes-base.code')) {
      assert.ok(sources[n.parameters.jsCode.trim()], `${n.name} is out of date with code/`);
    }
  });

  test(`${file}: no secrets or credential ids exported`, () => {
    const raw = JSON.stringify(wf);
    assert.doesNotMatch(raw, /sk-[A-Za-z0-9]{20,}|xox[bp]-/);
    for (const n of wf.nodes) assert.equal(n.credentials, undefined, `${n.name} has credentials attached`);
  });
}
