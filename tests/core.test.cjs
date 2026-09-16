const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname,'..');
const read = p => fs.readFileSync(path.join(root,p),'utf8');
const workerPromise = import('data:text/javascript;base64,'+Buffer.from(read('backend/worker.js')).toString('base64'));
const req = (p,origin,body='{}',headers={}) => new Request('https://example.test'+p,{method:'POST',headers:{...(origin?{origin}:{}),'content-type':'application/json',...headers},body});

test('investment IRR handles high returns, losses and ambiguous roots',()=>{
  const source=read('analizador.html');
  const code=source.slice(source.indexOf('function irr(cf)'),source.indexOf('\n\nfunction calc()'));
  const ctx=vm.createContext({});vm.runInContext(code,ctx);
  assert.ok(Math.abs(ctx.irr([-100,110])-.1)<1e-7);
  assert.ok(Math.abs(ctx.irr([-100,1000])-9)<1e-7);
  assert.ok(Math.abs(ctx.irr([-100,50])+.5)<1e-7);
  assert.equal(ctx.irr([-100,230,-132]),null);
  assert.equal(ctx.irr([0,0]),null);
  assert.equal(ctx.irr([-100,Infinity]),null);
});

test('all browser write routes reject unapproved origins before effects',async()=>{
  const {default:worker}=await workerPromise;
  for(const endpoint of ['claude','iris','texture','share','alerts','buscar','demand-log','vibra-log','ar-model']){
    const r=await worker.fetch(req('/api/'+endpoint,'https://unapproved.example'),{});
    assert.equal(r.status,403,endpoint);
  }
});
test('public widgets keep cross-origin read preflight',async()=>{
  const {default:worker}=await workerPromise;
  const r=await worker.fetch(new Request('https://example.test/api/score',{method:'OPTIONS',headers:{origin:'https://partner.example','access-control-request-method':'GET'}}),{});
  assert.equal(r.status,204);assert.equal(r.headers.get('access-control-allow-origin'),'*');
});
test('request byte limit applies when Content-Length is absent',async()=>{
  const {default:worker}=await workerPromise;
  const r=await worker.fetch(req('/api/share','https://brickbit.co','x'.repeat(512*1024+1)),{});
  assert.equal(r.status,413);
});
test('manual alert trigger no longer accepts credentials in URL',async()=>{
  const {default:worker}=await workerPromise;
  const r=await worker.fetch(req('/api/zone-alerts/run?key=test-only-key','https://brickbit.co'),{ALERT_TEST_KEY:'test-only-key'});
  assert.equal(r.status,403);
});
test('paid public routes have a bounded per-isolate burst limit',async()=>{
  const {default:worker}=await workerPromise;
  let response;
  for(let i=0;i<31;i++)response=await worker.fetch(req('/api/iris','https://brickbit.co','{}',{'cf-connecting-ip':'192.0.2.33'}),{});
  assert.equal(response.status,429);assert.equal(response.headers.get('retry-after'),'60');
});
test('Redis HTTP 200 command failure never becomes a successful save',async()=>{
  const {default:lead}=await import('../netlify/functions/lead.mjs');
  const savedFetch=global.fetch;
  process.env.UPSTASH_REDIS_REST_URL='https://redis.example';
  process.env.UPSTASH_REDIS_REST_TOKEN='test-only';
  global.fetch=async()=>new Response(JSON.stringify([{error:'simulated storage failure'}]),{status:200});
  try{
    const r=await lead(req('/api/lead',null,JSON.stringify({nombre:'Prueba local',telefono:'5500000000'})));
    assert.equal(r.status,500);assert.equal((await r.json()).ok,false);
  }finally{global.fetch=savedFetch;delete process.env.UPSTASH_REDIS_REST_URL;delete process.env.UPSTASH_REDIS_REST_TOKEN;}
});
test('lead deletion uses an atomic operation without rebuilding the list',async()=>{
  const {default:lead}=await import('../netlify/functions/lead.mjs');
  const savedFetch=global.fetch;let commands;
  Object.assign(process.env,{UPSTASH_REDIS_REST_URL:'https://redis.example',UPSTASH_REDIS_REST_TOKEN:'test-only',DIAG_ADMIN_TOKEN:'local-admin'});
  global.fetch=async(_,options)=>{commands=JSON.parse(options.body);return new Response(JSON.stringify([{result:2}]),{status:200});};
  try{
    const r=await lead(new Request('https://example.test/api/lead?telefono=5500000000',{method:'DELETE',headers:{'x-admin-token':'local-admin'}}));
    assert.equal(r.status,200);assert.equal((await r.json()).borrados,2);assert.equal(commands.length,1);assert.equal(commands[0][0],'EVAL');assert.ok(commands[0][1].includes("redis.call('LREM'"));
  }finally{global.fetch=savedFetch;for(const k of ['UPSTASH_REDIS_REST_URL','UPSTASH_REDIS_REST_TOKEN','DIAG_ADMIN_TOKEN'])delete process.env[k];}
});
test('invalid JSON shape is a client error in both lead forms',async()=>{
  for(const file of ['lead','diagnostico']){
    const {default:handler}=await import('../netlify/functions/'+file+'.mjs');
    assert.equal((await handler(req('/api/'+file,null,'null'))).status,400);
  }
});
