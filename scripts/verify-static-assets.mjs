import { readdirSync, readFileSync, existsSync, lstatSync } from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { fingerprint } from './ui-asset-names.mjs';

function files(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap(name => {
    const file = path.join(dir, name), stat = lstatSync(file);
    assert.ok(!stat.isSymbolicLink(), `Linked static source: ${file}`);
    return stat.isDirectory() ? files(file) : [file];
  });
}
// Runtime asset URLs must use the resolver. Ordinary CSS/import references are
// compiled by Vite; theme/download/external URLs are not UI-asset references.
export function verifySourceReferences(root) {
  for (const file of [...files(path.join(root, 'src')), path.join(root, 'index.html')]) {
    if (!existsSync(file) || !/\.(?:jsx?|tsx?|css|html)$/.test(file)) continue;
    const source = readFileSync(file, 'utf8');
    for (const match of source.matchAll(/(['"`])((?:\.\/|\/)?assets\/[^'"`\s]*)/g)) {
      const prefix = source.slice(Math.max(0, match.index - 25), match.index);
      const compiled = match[2].startsWith('./assets/') &&
        (/\b(?:from|import)\s*$/.test(prefix) || file.endsWith('.css') && /url\(\s*$/.test(prefix));
      assert.ok(compiled || match[2] === '/assets/LICENSE-Sarasa.txt', `Fixed UI URL in ${path.relative(root,file)}: ${match[2]}`);
    }
    assert.ok(!/\}assets\//.test(source), `Dynamic fixed UI URL in ${path.relative(root,file)}`);
    if (file.endsWith('.css')) assert.ok(!/url\(\s*\/?assets\//.test(source), `Fixed CSS UI URL in ${path.relative(root,file)}`);
  }
}
export function verifyStaticAssets(root) {
  verifySourceReferences(root);
  // Public downloads/legal files are an explicit reviewed compatibility surface,
  // not a second place to introduce mutable UI URLs.
  const baseline = JSON.parse(readFileSync(path.join(root, 'scripts/public-static-baseline.json'), 'utf8'));
  const publicFiles = files(path.join(root, 'public'));
  assert.deepEqual(publicFiles.map(p => path.relative(path.join(root,'public'),p).split(path.sep).join('/')).sort(), Object.keys(baseline).sort(), 'Unreviewed public static file');
  for (const [name, expected] of Object.entries(baseline)) {
    const bytes = readFileSync(path.join(root, 'public', name));
    assert.equal(createHash('sha256').update(bytes).digest('hex'), expected, `Published static bytes changed: ${name}`);
    assert.ok(readFileSync(path.join(root, 'dist/client', name)).equals(bytes), `Public output bytes changed: ${name}`);
  }
  const publicAssets = path.join(root, 'public/assets');
  if (existsSync(publicAssets)) assert.deepEqual(readdirSync(publicAssets).sort(), ['LICENSE-Sarasa.txt'], 'Fixed-name UI assets belong in src/assets');
  const source = path.join(root, 'src/assets'), output = path.join(root, 'dist/client/assets');
  const allowed = new Set();
  for (const file of files(source)) {
    assert.equal(path.dirname(file), source, 'UI assets must remain flat to avoid ambiguous resolver names');
    const bytes = readFileSync(file), expected = fingerprint(path.basename(file), bytes);
    allowed.add(expected);
    assert.ok(existsSync(path.join(output, expected)), `Missing SHA-256-named UI asset: ${expected}`);
    assert.ok(readFileSync(path.join(output, expected)).equals(bytes), `UI asset bytes changed: ${expected}`);
  }
  const manifestPath = path.join(root, 'dist/client/.vite/manifest.json');
  assert.ok(existsSync(manifestPath), 'Build manifest missing');
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  for (const entry of Object.values(manifest)) for (const name of [entry.file, ...(entry.css || [])]) {
    if (/^assets\/[^/]+-[A-Za-z0-9_-]{8}\.(?:js|css)$/.test(name || '')) allowed.add(name.slice(7));
  }
  const license = path.join(publicAssets, 'LICENSE-Sarasa.txt');
  if (existsSync(license)) {
    allowed.add('LICENSE-Sarasa.txt');
    assert.ok(readFileSync(path.join(output, 'LICENSE-Sarasa.txt')).equals(readFileSync(license)), 'License bytes changed');
  }
  assert.deepEqual(readdirSync(output).sort(), [...allowed].sort(), 'Unexpected or unhashed build asset');
  const expectedOutput = new Set(['index.html', '.vite/manifest.json', ...Object.keys(baseline), ...[...allowed].map(n => 'assets/' + n)]);
  const actualOutput = files(path.join(root,'dist/client')).map(p => path.relative(path.join(root,'dist/client'),p).split(path.sep).join('/'));
  assert.deepEqual(actualOutput.sort(), [...expectedOutput].sort(), 'Unexpected static build file');
}
