// Runs an n8n Code node file outside n8n by providing the globals it uses.
const fs = require('node:fs');
const path = require('node:path');

function runCodeNode(file, { json = {}, items = [], nodes = {} } = {}) {
  const src = fs.readFileSync(path.join(__dirname, '..', 'code', file), 'utf8');
  const $ = (name) => {
    if (!(name in nodes)) throw new Error(`node "${name}" not mocked`);
    return { item: { json: nodes[name] }, all: () => [{ json: nodes[name] }] };
  };
  const $input = { all: () => items.map((j) => ({ json: j })), item: { json } };
  // eslint-disable-next-line no-new-func
  const fn = new Function('$json', '$input', '$', `return (function(){ ${src} })();`);
  return fn(json, $input, $);
}

module.exports = { runCodeNode };
