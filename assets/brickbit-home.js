/* Shared-source explorer; no estimated value is presented as an observed sale. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const money = n => Number.isFinite(Number(n)) ? '$' + Math.round(Number(n)).toLocaleString('es-MX') : 'No disponible';
  const pct = n => (n >= 0 ? '+' : '') + n.toFixed(1) + '%';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let data = JSON.parse($('market-data').textContent), horizon = 3, favRequest = 0;
  const NS = 'http://www.w3.org/2000/svg';
  function svg(parent, tag, attrs, text) {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k,v]) => node.setAttribute(k, v));
    if (text != null) node.textContent = text;
    parent.appendChild(node); return node;
  }
  function render() {
    const city = $('exp-city').value;
    const z = data.estados.find(z => z.nombre === city), forecasts = data.forecast.zonas[city];
    if (!z || !forecasts || !forecasts[horizon]) return;
    const current = forecasts[horizon];
    $('exp-pm2').textContent = money(z.precio_m2);
    $('exp-growth').textContent = pct((current.f - 1) * 100);
    $('exp-horizon-label').textContent = `a ${horizon} año${horizon > 1 ? 's' : ''} · ${horizon > 3 ? 'extrapolación' : 'estimación'}`;
    $('exp-sub').textContent = 'Plusvalía histórica SHF: ' + pct(z.plusvalia) + ' anual';
    $('exp-analizar').href = 'analizador.html?zona=' + encodeURIComponent(city);
    const years = [0, 1, 3, 5, 10].filter(y => y <= horizon);
    const values = years.map(y => y ? forecasts[y] : { f:1, lo:1, hi:1 });
    const min = Math.min(...values.map(v => v.lo)) * z.precio_m2 * .96;
    const max = Math.max(...values.map(v => v.hi)) * z.precio_m2 * 1.03;
    const X = y => 65 + y / horizon * 567;
    const Y = v => 202 - (v * z.precio_m2 - min) / (max - min) * 172;
    const coords = key => values.map((v,i) => [X(years[i]), Y(v[key])]);
    const path = pts => pts.map((p,i) => `${i ? 'L' : 'M'}${p[0].toFixed(2)},${p[1].toFixed(2)}`).join(' ');
    const upper = coords('hi'), lower = coords('lo').reverse();
    $('chart-band').setAttribute('d', path(upper) + ' ' + path(lower).replace(/^M/,'L') + ' Z');
    $('chart-line').setAttribute('d', path(coords('f')));
    ['chart-grid', 'chart-labels', 'chart-points'].forEach(id => $(id).replaceChildren());
    for (let i=0;i<4;i++) {
      const value = min + (max-min) * i/3, y = 202-i/3*172;
      svg($('chart-grid'),'line',{x1:65,x2:632,y1:y,y2:y,stroke:'#29394e','stroke-dasharray':'3 5'});
      svg($('chart-labels'),'text',{x:56,y:y+4,'text-anchor':'end'},'$'+Math.round(value/1000)+'k');
    }
    years.forEach((year,i) => {
      svg($('chart-points'),'circle',{cx:X(year),cy:Y(values[i].f),r:i===0?4:3.5,fill:i===0?'#f2f6fc':'#F5C277',stroke:'#131e2e','stroke-width':2});
      svg($('chart-labels'),'text',{x:X(year),y:233,'text-anchor':'middle'},year===0?'2026':String(2026+year));
    });
    $('chart-title').textContent = `${city}: escenario a ${horizon} años`;
    $('chart-desc').textContent = `Referencia derivada ${money(z.precio_m2)} por m². Proyección ${money(z.precio_m2*current.f)}; intervalo nominal del 90% de ${money(z.precio_m2*current.lo)} a ${money(z.precio_m2*current.hi)}. Valores estimados. ${horizon>3?'Horizonte extrapolado sin validación.':'La cobertura retrospectiva fue '+(horizon===1?'91.5%':'86.6%')+'.'}`;
    $('data-source').textContent = `Referencia de precio: mediana estatal SHF / superficie media ENVI 2020; no es una transacción observada. Fuente de plusvalía: ${z.fuentes.plusvalia}. Pronóstico generado: ${data.forecast.meta.generado}, origen ${data.forecast.meta.origen}.`;
    document.querySelectorAll('[data-h]').forEach(b => b.setAttribute('aria-pressed',Number(b.dataset.h)===horizon));
    updateFavorite();
  }
  async function updateFavorite() {
    const seq = ++favRequest, city = $('exp-city').value;
    $('exp-fav').textContent = 'Guardar zona'; $('fav-status').textContent = '';
    if (typeof bbIsFav !== 'function') return;
    try { const saved = await bbIsFav(city); if(seq===favRequest) $('exp-fav').textContent = saved?'Zona guardada ✓':'Guardar zona'; } catch { /* Retry is available on the save action. */ }
  }
  $('exp-city').addEventListener('change',render);
  document.querySelectorAll('[data-h]').forEach(b => b.addEventListener('click',() => { horizon=Number(b.dataset.h); render(); }));
  $('exp-fav').addEventListener('click',async () => {
    if(typeof bbUser!=='function') { $('fav-status').textContent='La sesión no está disponible. Recarga la página.'; return; }
    if(!await bbUser()) { openAuthModal('in'); return; }
    const city=$('exp-city').value, btn=$('exp-fav'); btn.disabled=true;
    try { await bbFavToggle(city); await updateFavorite(); }
    catch(e) { $('fav-status').textContent=e.message; }
    finally { btn.disabled=false; }
  });
  if(typeof mountAuth==='function') mountAuth('auth-slot');
  if(typeof bbOnAuth==='function') bbOnAuth(updateFavorite);
  render();
  // The embedded snapshot gives a useful first paint; refresh atomically.
  Promise.all(['data/estados.json','data/forecast.json'].map(async url => {
    const r=await fetch(url,{cache:'no-cache'}); if(!r.ok) throw new Error('Datos no disponibles'); return r.json();
  })).then(([states,forecast]) => {
    if(!Array.isArray(states.estados) || !forecast.zonas) throw new Error('Formato de datos no válido');
    data={estados:states.estados,forecast}; render();
  }).catch(() => { $('data-source').textContent += ' No se pudo actualizar: se muestra la copia incluida con esta versión.'; });

  const menu=$('menu-toggle'), sidebar=$('sidebar');
  function closeMenu(){ sidebar.classList.remove('open'); menu.setAttribute('aria-expanded','false'); menu.setAttribute('aria-label','Abrir navegación'); }
  menu.addEventListener('click',() => {
    const open=sidebar.classList.toggle('open'); menu.setAttribute('aria-expanded',open); menu.setAttribute('aria-label',open?'Cerrar navegación':'Abrir navegación');
  });
  sidebar.addEventListener('click',e=>{if(e.target.closest('a'))closeMenu();});
  document.addEventListener('keydown',e=>{if(e.key==='Escape' && sidebar.classList.contains('open')){closeMenu();menu.focus();}});
  document.addEventListener('click',e=>{if(!sidebar.contains(e.target) && !menu.contains(e.target))closeMenu();});
  const video=$('city-video'), videoButton=$('video-toggle');
  videoButton.addEventListener('click',async()=>{
    if(!video.paused){video.pause();return;}
    try{await video.play();}catch{videoButton.textContent='Video no disponible';}
  });
  video.addEventListener('play',()=>{videoButton.textContent='Pausar';});
  video.addEventListener('pause',()=>{videoButton.textContent='Reproducir';});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)video.pause();});
  reduced.addEventListener('change',()=>{if(reduced.matches)video.pause();});

  // All external content is textContent. URLs must explicitly be HTTP(S).
  function safeURL(value){try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)?url.href:null;}catch{return null;}}
  function el(tag, cls, text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=text;return n;}
  function propertyCard(x){
    const card=el('article','result-card'), imgURL=safeURL(x.imagen);
    if(imgURL){const img=el('img');img.src=imgURL;img.alt=x.titulo||'Inmueble';img.loading='lazy';img.referrerPolicy='no-referrer';card.append(img);}
    const body=el('div','result-body');
    body.append(el('div','result-price',money(x.precio)+' '+(x.moneda||'MXN')+(x.operacion==='renta'?' / mes':'')),el('h3','',x.titulo||x.tipo||'Inmueble'));
    body.append(el('p','',[x.municipio,x.zona].filter(Boolean).join(', ')));
    body.append(el('p','',[x.tipo,x.recamaras?x.recamaras+' recámaras':null,x.m2_construccion?x.m2_construccion+' m²':null].filter(Boolean).join(' · ')));
    if(x.zona_yield!=null)body.append(el('p','estimate','Rendimiento de zona: '+x.zona_yield+'% · referencia, no rendimiento del inmueble'));
    if(x.tesis)body.append(el('p','',x.tesis));
    if(x.riesgo)body.append(el('p','estimate','Riesgo: '+x.riesgo));
    const url=safeURL(x.url);if(url){const a=el('a','','Consultar ficha original ↗');a.href=url;a.target='_blank';a.rel='noopener noreferrer';body.append(a);}
    card.append(body);return card;
  }
  let searchController=null;
  $('close-results').addEventListener('click',()=>{if(searchController)searchController.abort();$('buscador').hidden=true;$('bsc-q').focus();});
  $('search-form').addEventListener('submit',async e=>{
    e.preventDefault();const q=$('bsc-q').value.trim();if(!q)return;
    if(searchController)searchController.abort();
    const controller=new AbortController();searchController=controller;
    const out=$('bsc-out'),button=$('bsc-go');$('buscador').hidden=false;
    out.replaceChildren(el('p','result-note','Buscando inmuebles…'));button.disabled=true;out.setAttribute('aria-busy','true');
    const timer=setTimeout(()=>controller.abort(),60000);
    try{
      const r=await fetch('https://brickbit-api.jose-delgado-enp.workers.dev/api/buscar',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({q}),signal:controller.signal});
      if(!r.ok)throw new Error('El buscador no está disponible en este momento. Intenta de nuevo.');
      const j=await r.json();out.replaceChildren();
      if(j.interpretacion)out.append(el('p','result-note',j.interpretacion));
      const pf=j.portafolio;
      if(pf){
        if(pf.error||pf.vacio)out.append(el('p','result-note',pf.error?'No se pudo armar el portafolio.':'No hay propiedades para ese presupuesto. Prueba otra zona o cantidad.'));
        else if(Array.isArray(pf.piezas)&&pf.piezas.length){
          out.append(el('h3','','Portafolio sugerido'),el('p','result-note',`${money(pf.invertido)} asignados · ${money(pf.sin_asignar)} sin asignar. ${pf.resumen||''}`));
          const portfolio=el('div','result-grid');pf.piezas.forEach(p=>portfolio.append(propertyCard(p)));out.append(portfolio);
          if(pf.siguiente_paso)out.append(el('p','result-note',pf.siguiente_paso));
        }
      }
      const results=Array.isArray(j.resultados)?j.resultados:[];
      out.append(el('p','result-note',results.length?`${j.total??results.length} resultados encontrados`:'Sin resultados con esos filtros. Prueba otra zona o presupuesto.'));
      const grid=el('div','result-grid');results.forEach(x=>grid.append(propertyCard(x)));out.append(grid);
      out.append(el('p','data-source','Las comparaciones de precio y rendimiento son estimaciones. El rendimiento de una zona no es el de cada propiedad. Consulta la ficha original y verifica sus condiciones.'));
    }catch(e){out.replaceChildren(el('p','result-note',e.name==='AbortError'?'La búsqueda se interrumpió. Puedes intentarlo de nuevo.':e.message));}
    finally{clearTimeout(timer);if(searchController===controller){button.disabled=false;out.removeAttribute('aria-busy');searchController=null;}}
  });
  $('waitlist-form').addEventListener('submit',async e=>{
    e.preventDefault();const form=e.currentTarget,button=form.querySelector('button'),status=$('wait-status');button.disabled=true;
    try{
      const r=await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(form))});
      if(!r.ok)throw new Error('No se pudo registrar el correo. Intenta de nuevo.');
      status.textContent='Correo registrado. Te avisaremos de las novedades.';form.reset();
    }catch(e){status.textContent=e.message;}finally{button.disabled=false;}
  });
})();
