/* ============================================================
   BrickBit · auth.js — autenticación compartida (Supabase)
   ------------------------------------------------------------
   1) Crea tu proyecto en supabase.com
   2) Project Settings → API → copia Project URL y anon public key
   3) Pégalas AQUÍ ABAJO (la anon key es pública: segura en el cliente,
      porque la seguridad real la da Row Level Security en Supabase)
   ============================================================ */
const SUPABASE_URL      = 'https://flhaljaeynzsenjsyuym.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZsaGFsamFleW56c2VuanN5dXltIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE5MTYxOTYsImV4cCI6MjA5NzQ5MjE5Nn0.rsA_iI4eHcq23ohPU_XmN98YlNu-H4BrGZiSGx5JDeY';

/* ---- init robusto: espera a que la librería Supabase esté disponible ---- */
let sb = null;
let bbChipEl = null;        // declarado aquí para que el init pueda referenciarlo
window.bbConfigured = false;
function bbTryInit(){
  if (sb) return true;
  try{
    if (window.supabase && typeof window.supabase.createClient === 'function'
        && /^https:\/\/.+\.supabase\.co/.test(SUPABASE_URL) && SUPABASE_ANON_KEY.length > 20){
      sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
      window.bbConfigured = true;
      return true;
    }
  }catch(e){ console.warn('[BrickBit auth] Supabase no inicializado:', e); }
  return false;
}
(function waitForSupabase(tries){
  if (bbTryInit()){
    if (bbChipEl){ injectAuthCSS(); renderAuthChip(); bbOnAuth(()=>renderAuthChip()); }
    return;
  }
  if (tries > 0) setTimeout(()=>waitForSupabase(tries-1), 100); // reintenta hasta ~6s
})(60);

/* ---- helpers (úsalos desde cualquier página) ---- */
async function bbUser(){ if(!sb) return null; try{ const {data}=await sb.auth.getUser(); return data&&data.user||null; }catch(e){ return null; } }
async function bbSignUp(email, password, nombre){ if(!sb) throw new Error('Supabase no configurado'); return sb.auth.signUp({ email, password, options:{ data:{ nombre: nombre||'' } } }); }
async function bbSignIn(email, password){ if(!sb) throw new Error('Supabase no configurado'); return sb.auth.signInWithPassword({ email, password }); }
async function bbGoogle(){ if(!sb) throw new Error('Supabase no configurado'); return sb.auth.signInWithOAuth({ provider:'google', options:{ redirectTo: location.origin + location.pathname } }); }
async function bbSignOut(){ if(!sb) return; await sb.auth.signOut(); renderAuthChip(); }
function bbOnAuth(cb){ if(sb) sb.auth.onAuthStateChange((_e, session)=> cb(session && session.user || null)); }
function bbClient(){ return sb; }

/* ---- favoritos de zonas (tabla favorite_zones, protegida por RLS) ---- */
let bbFavCache=null;
if(sb){ try{ sb.auth.onAuthStateChange(()=>{ bbFavCache=null; }); }catch(e){} }
async function bbFavs(force){
  if(!sb) return [];
  const u=await bbUser(); if(!u){ bbFavCache=null; return []; }
  if(bbFavCache && !force) return bbFavCache;
  const {data,error}=await sb.from('favorite_zones').select('zona');
  if(error){ console.warn('[BrickBit favs]', error.message); return bbFavCache||[]; }
  bbFavCache=(data||[]).map(r=>r.zona);
  return bbFavCache;
}
async function bbIsFav(zona){ const f=await bbFavs(); return f.indexOf(zona)>=0; }
async function bbFavAdd(zona){ if(!sb) return false; const u=await bbUser(); if(!u) return false; const {error}=await sb.from('favorite_zones').insert({ user_id:u.id, zona }); if(error){ console.warn(error.message); return false; } if(bbFavCache && bbFavCache.indexOf(zona)<0) bbFavCache.push(zona); return true; }
async function bbFavRemove(zona){ if(!sb) return false; const u=await bbUser(); if(!u) return false; const {error}=await sb.from('favorite_zones').delete().eq('zona', zona); if(error){ console.warn(error.message); return false; } if(bbFavCache) bbFavCache=bbFavCache.filter(z=>z!==zona); return true; }
async function bbFavToggle(zona){ const is=await bbIsFav(zona); if(is){ await bbFavRemove(zona); return false; } await bbFavAdd(zona); return true; }

/* ---- estilos del chip + modal (se inyectan una vez) ---- */
function injectAuthCSS(){
  if(document.getElementById('bb-auth-css')) return;
  const s=document.createElement('style'); s.id='bb-auth-css';
  s.textContent=`
  .bb-chip{display:inline-flex;align-items:center;gap:7px;font-family:inherit;font-size:12.5px}
  .bb-btn{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:7px 14px;font-size:12.5px;font-weight:600;cursor:pointer;font-family:inherit;border:1px solid rgba(45,212,155,.4);background:#0C1218;color:#2DD49B;transition:border-color .2s}
  .bb-btn:hover{border-color:#2DD49B}
  .bb-btn-primary{background:linear-gradient(135deg,#1a7d50,#2DD49B);color:#06140d;border:none}
  .bb-user{color:#cabbab}.bb-user b{color:#f5ede3}
  .bb-link{background:none;border:none;color:#8FA3A0;cursor:pointer;font-size:11.5px;text-decoration:underline;font-family:inherit;padding:0}
  .bb-ov{position:fixed;inset:0;background:rgba(6,8,6,.72);z-index:5000;display:none;align-items:center;justify-content:center;padding:18px;backdrop-filter:blur(3px)}
  .bb-ov.on{display:flex}
  .bb-modal{width:100%;max-width:380px;background:#15100c;border:1px solid rgba(45,212,155,.25);border-radius:18px;padding:26px 24px;box-shadow:0 24px 70px rgba(0,0,0,.6);position:relative;font-family:'Hanken Grotesk',system-ui,sans-serif}
  .bb-x{position:absolute;top:12px;right:14px;background:none;border:none;color:#8FA3A0;font-size:18px;cursor:pointer;line-height:1}
  .bb-title{font-family:'Fraunces',serif;font-size:21px;color:#f5ede3;margin:0 0 4px}
  .bb-sub{font-size:12.5px;color:#8FA3A0;margin:0 0 18px}
  .bb-tabs{display:flex;gap:6px;margin-bottom:16px}
  .bb-tab{flex:1;padding:8px;border-radius:9px;border:1px solid rgba(245,237,227,.12);background:transparent;color:#a89a8c;font-size:12.5px;font-weight:600;cursor:pointer;font-family:inherit}
  .bb-tab.on{background:rgba(45,212,155,.12);border-color:#2DD49B;color:#2DD49B}
  .bb-fld{margin-bottom:11px}
  .bb-fld label{display:block;font-size:11px;color:#a89a8c;margin-bottom:4px}
  .bb-fld input{width:100%;background:#0e0a07;border:1px solid rgba(245,237,227,.14);color:#f5ede3;border-radius:9px;padding:10px 12px;font-size:13.5px;font-family:inherit;outline:none;box-sizing:border-box}
  .bb-fld input:focus{border-color:#2DD49B}
  .bb-google{width:100%;display:flex;align-items:center;justify-content:center;gap:9px;background:#fff;color:#1f1f1f;border:none;border-radius:9px;padding:11px;font-size:13.5px;font-weight:600;cursor:pointer;font-family:inherit;margin-top:4px}
  .bb-submit{width:100%;margin-top:6px;border-radius:9px;padding:11px;font-size:13.5px;font-weight:700;cursor:pointer;border:none;background:linear-gradient(135deg,#1a7d50,#2DD49B);color:#06140d;font-family:inherit}
  .bb-submit:disabled{opacity:.6;cursor:default}
  .bb-or{display:flex;align-items:center;gap:10px;color:#8FA3A0;font-size:11px;margin:14px 0}
  .bb-or::before,.bb-or::after{content:'';flex:1;height:1px;background:rgba(245,237,227,.1)}
  .bb-msg{font-size:12px;margin-top:10px;min-height:1em}
  .bb-msg.err{color:#F08886}.bb-msg.ok{color:#cdf25a}
  `;
  document.head.appendChild(s);
}

/* ---- modal (se construye una vez) ---- */
function buildAuthModal(){
  if(document.getElementById('bb-ov')) return;
  const ov=document.createElement('div'); ov.className='bb-ov'; ov.id='bb-ov';
  ov.innerHTML=`
   <div class="bb-modal" role="dialog" aria-modal="true">
     <button class="bb-x" onclick="closeAuthModal()" aria-label="Cerrar">✕</button>
     <h3 class="bb-title" id="bb-title">Entra a BrickBit</h3>
     <p class="bb-sub">Guarda tus análisis y tus zonas favoritas.</p>
     <div class="bb-tabs">
       <button class="bb-tab on" id="bb-tab-in"  onclick="switchAuthTab('in')">Entrar</button>
       <button class="bb-tab"    id="bb-tab-up"  onclick="switchAuthTab('up')">Crear cuenta</button>
     </div>
     <button class="bb-google" onclick="bbGoogleClick()">
       <svg width="17" height="17" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.3 6.1 29.4 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.3-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 16 19 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.3 6.1 29.4 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.5-5.2l-6.2-5.3C29.2 35 26.7 36 24 36c-5.3 0-9.7-3.3-11.3-8l-6.5 5C9.6 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.2-4.1 5.5l6.2 5.3C39.9 35.7 44 30.4 44 24c0-1.3-.1-2.3-.4-3.5z"/></svg>
       Continuar con Google
     </button>
     <div class="bb-or">o con tu correo</div>
     <div class="bb-fld" id="bb-fld-nombre" style="display:none"><label>Nombre</label><input id="bb-nombre" type="text" autocomplete="name" placeholder="Tu nombre"></div>
     <div class="bb-fld"><label>Correo</label><input id="bb-email" type="email" autocomplete="email" placeholder="tu@correo.com"></div>
     <div class="bb-fld"><label>Contraseña</label><input id="bb-pass" type="password" autocomplete="current-password" placeholder="••••••••"></div>
     <button class="bb-submit" id="bb-submit" onclick="submitAuth()">Entrar</button>
     <div class="bb-msg" id="bb-msg" role="status"></div>
   </div>`;
  document.body.appendChild(ov);
  ov.addEventListener('click', e=>{ if(e.target===ov) closeAuthModal(); });
}

let bbTab='in';
function openAuthModal(tab){ injectAuthCSS(); buildAuthModal(); switchAuthTab(tab||'in'); document.getElementById('bb-ov').classList.add('on'); }
function closeAuthModal(){ const o=document.getElementById('bb-ov'); if(o) o.classList.remove('on'); const m=document.getElementById('bb-msg'); if(m){m.textContent='';m.className='bb-msg';} }
function switchAuthTab(t){
  bbTab=t;
  const inT=document.getElementById('bb-tab-in'), upT=document.getElementById('bb-tab-up');
  if(inT&&upT){ inT.classList.toggle('on',t==='in'); upT.classList.toggle('on',t==='up'); }
  const nombre=document.getElementById('bb-fld-nombre'); if(nombre) nombre.style.display = t==='up'?'block':'none';
  const sub=document.getElementById('bb-submit'); if(sub) sub.textContent = t==='up'?'Crear cuenta':'Entrar';
  const title=document.getElementById('bb-title'); if(title) title.textContent = t==='up'?'Crea tu cuenta':'Entra a BrickBit';
  const pass=document.getElementById('bb-pass'); if(pass) pass.setAttribute('autocomplete', t==='up'?'new-password':'current-password');
}
function authMsg(text, kind){ const m=document.getElementById('bb-msg'); if(m){ m.textContent=text; m.className='bb-msg '+(kind||''); } }

async function bbGoogleClick(){
  if(!sb){ authMsg('Configura Supabase en auth.js para activar el login.','err'); return; }
  try{ await bbGoogle(); }catch(e){ authMsg(e.message||'No se pudo iniciar sesión con Google.','err'); }
}
async function submitAuth(){
  if(!sb){ authMsg('Configura Supabase en auth.js para activar el login.','err'); return; }
  const email=(document.getElementById('bb-email').value||'').trim();
  const pass=document.getElementById('bb-pass').value||'';
  const nombre=(document.getElementById('bb-nombre')&&document.getElementById('bb-nombre').value||'').trim();
  if(!email || !pass){ authMsg('Escribe tu correo y contraseña.','err'); return; }
  const btn=document.getElementById('bb-submit'); btn.disabled=true; authMsg('Un momento…');
  try{
    if(bbTab==='up'){
      const {error}=await bbSignUp(email,pass,nombre); if(error) throw error;
      authMsg('¡Cuenta creada! Revisa tu correo si te pedimos confirmarla.','ok');
    }else{
      const {error}=await bbSignIn(email,pass); if(error) throw error;
      authMsg('¡Listo!','ok');
    }
    setTimeout(()=>{ closeAuthModal(); renderAuthChip(); }, 600);
  }catch(e){
    authMsg(e.message||'No se pudo completar. Verifica tus datos.','err');
  }finally{ btn.disabled=false; }
}

/* ---- chip de usuario (login / sesión) ---- */
function mountAuth(elId){
  bbChipEl=document.getElementById(elId); if(!bbChipEl) return;
  if(!sb){ bbChipEl.innerHTML=''; return; }     // sin configurar → no muestra nada
  injectAuthCSS();
  renderAuthChip();
  bbOnAuth(()=>renderAuthChip());
}
async function renderAuthChip(){
  if(!bbChipEl) return;
  if(!sb){ bbChipEl.innerHTML=''; return; }
  const u=await bbUser();
  if(u){
    const nombre=(u.user_metadata&&u.user_metadata.nombre)||u.email;
    bbChipEl.innerHTML=`<span class="bb-chip"><span class="bb-user">Hola, <b>${escapeHtml(nombre)}</b></span> <a class="bb-link" href="panel.html" style="text-decoration:none">Mi BrickBit</a> <button class="bb-link" onclick="bbSignOut()">Salir</button></span>`;
  }else{
    bbChipEl.innerHTML=`<button class="bb-btn" onclick="openAuthModal('in')">Entrar / Crear cuenta</button>`;
  }
}
function escapeHtml(s){ return String(s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
