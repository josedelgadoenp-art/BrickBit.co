const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
const root=path.resolve(__dirname,'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function home(searchResult){
  const {window,document}=parseHTML(read('index.html'));
  // Linkedom does not implement the native select value setter.
  const select=document.getElementById('exp-city');let city='Ciudad de México';
  Object.defineProperty(select,'value',{get:()=>city,set:v=>city=v});
  const ctx=vm.createContext({document,window,URL,URLSearchParams,FormData,AbortController,console,setTimeout,clearTimeout,
    matchMedia:()=>({matches:true,addEventListener(){}}),
    fetch:async url=>new Response(JSON.stringify(String(url).startsWith('data/')?JSON.parse(read(url)):searchResult),{status:200})});
  vm.runInContext(read('assets/brickbit-home.js'),ctx);return {window,document,select};
}
test('city and horizon interactions follow the canonical forecast, not stale constants',async()=>{
  const {window,document,select}=home({});await tick();
  assert.equal(document.getElementById('exp-growth').textContent,'+16.0%');
  select.value='Cancún';select.dispatchEvent(new window.Event('change'));
  assert.equal(document.getElementById('exp-growth').textContent,'+26.1%');
  document.querySelector('[data-h="10"]').click();
  assert.equal(document.getElementById('exp-growth').textContent,'+116.6%');
  assert.match(document.getElementById('chart-desc').textContent,/sin validación/);
  assert.equal(new URL(document.getElementById('exp-analizar').getAttribute('href'),'https://example.test').searchParams.get('zona'),'Cancún');
  assert.ok(document.getElementById('chart-band').getAttribute('d').endsWith('Z'));
});
test('search output treats external HTML as text and rejects executable URLs',async()=>{
  const {window,document}=home({interpretacion:'<img src=x onerror=alert(1)>',total:1,resultados:[{titulo:'<script>alert(1)</script>',precio:100,url:'javascript:alert(1)',imagen:'javascript:alert(2)'}]});
  await tick();document.getElementById('bsc-q').value='departamento';
  document.getElementById('search-form').dispatchEvent(new window.Event('submit',{cancelable:true}));
  await tick();const out=document.getElementById('bsc-out');
  assert.equal(out.querySelectorAll('script,img,a[href^="javascript:"]').length,0);
  assert.match(out.textContent,/<script>alert/);
  assert.equal(document.getElementById('bsc-go').disabled,false);
});
test('mobile navigation exposes its state and closes with Escape',()=>{
  const {window,document}=home({});const menu=document.getElementById('menu-toggle');menu.focus=()=>{};
  menu.click();assert.equal(menu.getAttribute('aria-expanded'),'true');
  const event=new window.Event('keydown');event.key='Escape';document.dispatchEvent(event);
  assert.equal(menu.getAttribute('aria-expanded'),'false');
});
