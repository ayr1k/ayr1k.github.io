// Run in disposable CI with a pinned Playwright installation, not a personal browser.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve, sep} from 'node:path';
import {pathToFileURL} from 'node:url';
const {chromium} = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const root = resolve('dist/client');
const server = createServer(async (request, response) => {
  try {
    const pathname = new URL(request.url, 'http://test').pathname;
    const target = resolve(root, '.' + (pathname === '/' ? '/index.html' : decodeURIComponent(pathname)));
    if (!target.startsWith(root + sep)) throw new Error('path');
    const body = await readFile(target);
    const extension = target.split('.').pop();
    const type = {html:'text/html',js:'text/javascript',css:'text/css',json:'application/json',woff2:'font/woff2'}[extension];
    response.writeHead(200, {'Content-Type': type || 'application/octet-stream'}).end(body);
  } catch {response.writeHead(404).end();}
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({headless:true});
const suffixes = ['Setup-x64.exe','mac-x64.zip','mac-arm64.zip','linux-x64.deb','freebsd-x64-experimental.tar.gz'];
const index = {schema:1,products:{}};
for (const [product, repo] of [['AMBER','ayr1k/amber-launcher'],['AmberE','ayr1k/AmberE']]) {
  index.products[product] = {repo,versions:{}};
  for (const version of ['1.7.10','1.8.0']) {
    index.products[product].versions[version] = {files:Object.fromEntries(suffixes.map(suffix => {
      const name = `${product}-${version}-${suffix}`;
      return [name,{size:123,sha256:'a'.repeat(64),path:`/mirror/v1/${product.toLowerCase()}/${version}/${name}`}];
    }))};
  }
}
let assertions = 0;
try {
  for (const lang of ['zh','en']) for (const product of ['AMBER','AmberE']) for (const mobile of [false,true]) {
    const context = await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1440,height:1000}});
    await context.addInitScript(language => localStorage.setItem('amber-site-language',language),lang);
    const page = await context.newPage();
    const errors=[]; page.on('pageerror',error=>errors.push(error.message));
    await page.route('https://amber.ayuki-ayr1k.com/**',route=>route.fulfill(
      route.request().method()==='HEAD'?{status:200,headers:{'content-length':'123','access-control-allow-origin':'*'}}:
      {status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify(index)}));
    await page.goto(base+'/#/download'+(product==='AmberE'?'?product=ambere':''));
    await page.waitForFunction(()=>document.querySelectorAll('.mirror-download').length===5);
    const links=await page.locator('.platform-actions a').evaluateAll(nodes=>nodes.map(a=>a.href));
    assert.equal(links.length,10);
    for(const suffix of suffixes){
      const name=`${product}-1.7.10-${suffix}`;
      assert.ok(links.some(url=>url===`https://github.com/${index.products[product].repo}/releases/download/v1.7.10/${name}`));
      assert.ok(links.some(url=>url===`https://amber.ayuki-ayr1k.com/mirror/v1/${product.toLowerCase()}/1.7.10/${name}`));
      assertions+=2;
    }
    assert.ok(links.every(url=>!url.includes('1.8.0')));
    assert.equal(await page.locator('.platform-download').count(),4);
    assert.equal(await page.locator('html').getAttribute('lang'),lang==='en'?'en':'zh-CN');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.deepEqual(errors,[]);
    await context.close(); assertions+=5;
  }
  for(const scenario of ['api-failure','missing-mirror','different-version','partial-platforms']){
    const context=await browser.newContext(); const page=await context.newPage();
    await page.route('https://amber.ayuki-ayr1k.com/**',async route=>{
      if(scenario==='api-failure') return route.fulfill({status:503,headers:{'access-control-allow-origin':'*'}});
      const data=structuredClone(index);
      if(scenario==='different-version') delete data.products.AMBER.versions['1.7.10'];
      if(scenario==='partial-platforms') delete data.products.AMBER.versions['1.7.10'].files['AMBER-1.7.10-mac-arm64.zip'];
      return route.fulfill(route.request().method()==='HEAD'?{
        status:scenario==='missing-mirror'?404:200,headers:{'content-length':'123','access-control-allow-origin':'*'}
      }:{status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify(data)});
    });
    await page.goto(base+'/#/download');
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('.platform-actions a[href^="https://github.com/"]').count(),5);
    assert.equal(await page.locator('.mirror-download').count(),scenario==='partial-platforms'?4:0);
    await context.close(); assertions+=2;
  }
  console.log(`Browser download checks passed: ${assertions} assertions; both products/languages, desktop/mobile, unavailable and partial mirrors.`);
} finally {await browser.close(); server.close();}
