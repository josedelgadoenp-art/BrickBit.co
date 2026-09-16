const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');
function auth(){
  const {window,document}=parseHTML('<html><head></head><body></body></html>');
  let fail=false,user='one';const callbacks=[];
  const client={auth:{onAuthStateChange:fn=>callbacks.push(fn),getUser:async()=>({data:{user:{id:user}}})},
    from:()=>({select:async()=>({data:[{zona:user==='one'?'Cancún':'Mérida'}]}),insert:async()=>({error:fail?{message:'test write failure'}:null})})};
  window.supabase={createClient:()=>client};
  const ctx=vm.createContext({window,document,console:{warn(){}},setTimeout(){},clearTimeout});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../auth.js'),'utf8'),ctx);
  return {ctx,setFailure:()=>{fail=true;},switchUser:()=>{user='two';callbacks.forEach(fn=>fn('SIGNED_IN',{user:{id:user}}));}};
}
test('favorite write failure cannot be reported as saved',async()=>{
  const {ctx,setFailure}=auth();setFailure();
  await assert.rejects(ctx.bbFavToggle('Monterrey'),/No se pudo guardar/);
});
test('favorite cache cannot leak a previous account list',async()=>{
  const {ctx,switchUser}=auth();
  assert.deepEqual(Array.from(await ctx.bbFavs()),['Cancún']);switchUser();
  assert.deepEqual(Array.from(await ctx.bbFavs()),['Mérida']);
});
