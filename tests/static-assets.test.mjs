import test from 'node:test';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { verifyStaticAssets } from '../scripts/verify-static-assets.mjs';
import { fingerprint } from '../scripts/ui-asset-names.mjs';
function fixture(t) {
  const root = mkdtempSync(path.join(tmpdir(), 'amber-ui-assets-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  for (const dir of ['src/assets','public/assets','dist/client/assets','dist/client/.vite','scripts']) mkdirSync(path.join(root, dir), { recursive: true });
  const write = (name, bytes) => writeFileSync(path.join(root, name), bytes);
  write('scripts/public-static-baseline.json',JSON.stringify({'assets/LICENSE-Sarasa.txt':createHash('sha256').update('license').digest('hex')}));write('dist/client/index.html','<html/>');
  write('public/assets/LICENSE-Sarasa.txt', 'license');write('dist/client/assets/LICENSE-Sarasa.txt', 'license');
  write('dist/client/.vite/manifest.json', '{}');
  const asset = (name, bytes) => {write('src/assets/'+name,bytes);write('dist/client/assets/'+fingerprint(name,bytes),bytes);};
  asset('example.svg', '<svg/>');
  return { root, write, asset };
}
test('every UI format uses exact SHA-256 names and bytes', t => {
  const {root, asset} = fixture(t);for (const ext of ['woff2','webp','png']) asset('new.'+ext,'bytes');verifyStaticAssets(root);
  assert.notEqual(fingerprint('new.svg','old'),fingerprint('new.svg','changed'));
});
test('future fixed-name public UI assets fail the build', t => {
  const {root, write} = fixture(t);write('public/assets/new-icon.svg','<svg/>');assert.throws(() => verifyStaticAssets(root), /Unreviewed public static file/);
});
test('fixed and forged-hash names cannot stand in for content hashes', t => {
  const {root, write} = fixture(t);rmSync(path.join(root,'dist/client/assets',fingerprint('example.svg','<svg/>')));
  for(const name of ['example-fixed.svg','example-1234567890abcdef.svg']) write('dist/client/assets/'+name,'<svg/>');
  assert.throws(() => verifyStaticAssets(root), /Missing SHA-256/);
});
test('unexpected extra output is rejected even when expected assets exist', t => {
  const {root, write} = fixture(t);write('dist/client/assets/hidden.svg','<svg/>');assert.throws(() => verifyStaticAssets(root), /Unexpected/);
});
test('changed output bytes fail closed', t => {
  const {root, write} = fixture(t);write('dist/client/assets/'+fingerprint('example.svg','<svg/>'),'changed');assert.throws(() => verifyStaticAssets(root), /bytes changed/);
});
for(const code of ['const img="/assets/example.svg";', 'const img="assets/example.svg";', 'const img=`${import.meta.env.BASE_URL}assets/${name}`;', 'const img="/assets/"+name;']) test('fixed or concatenated source URL is rejected: '+code,t=>{
 const {root,write}=fixture(t);write('src/Bad.jsx',code);assert.throws(()=>verifyStaticAssets(root),/Fixed UI URL|Dynamic fixed UI URL/);
});
test('compiled imports, resolver, license, theme and external URLs remain supported',t=>{
 const {root,write}=fixture(t);
 write('src/Good.jsx',"import img from './assets/example.svg'; const download=`/themes/${name}`; const external='https://example.com/assets/pic.svg'; const license='/assets/LICENSE-Sarasa.txt'; const resolver=urls[`/src/assets/${name}`];");
 write('src/Good.css',"x{background:url('./assets/example.svg')}");verifyStaticAssets(root);
});
test('only manifest-listed Vite JS/CSS outputs are allowed',t=>{
 const {root,write}=fixture(t);write('dist/client/assets/index-abcdefgh.js','export{}');assert.throws(()=>verifyStaticAssets(root),/Unexpected/);
 write('dist/client/.vite/manifest.json',JSON.stringify({'index.html':{file:'assets/index-abcdefgh.js',isEntry:true}}));verifyStaticAssets(root);
});

test('new public paths and changed published bytes require explicit baseline review',t=>{
 const {root,write}=fixture(t);write('public/new.svg','new');assert.throws(()=>verifyStaticAssets(root),/Unreviewed public/);rmSync(path.join(root,'public/new.svg'));
 write('public/assets/LICENSE-Sarasa.txt','changed');assert.throws(()=>verifyStaticAssets(root),/Published static bytes changed/);
});
test('extra output outside assets is also rejected',t=>{
 const {root,write}=fixture(t);write('dist/client/extra.svg','extra');assert.throws(()=>verifyStaticAssets(root),/Unexpected static build file/);
});
