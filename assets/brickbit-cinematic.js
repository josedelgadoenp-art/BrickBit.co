/* Real video from Higgsfield; native controls remain available on every device. */
(() => {
  'use strict';
  const film=document.getElementById('territory-film');if(!film)return;
  const play=document.getElementById('territory-play'),toggle=document.getElementById('motion-toggle'),status=document.getElementById('territory-media-status');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)'),root=document.documentElement;
  let manualReduced=false,loaded=false,pendingSeek=null,active=0;
  try{manualReduced=localStorage.getItem('bb-motion')==='reduce';}catch{}
  const chapters=[
    {copy:'Conoce el mercado antes de elegir una propiedad.',label:'Mapa de México ↗',href:'mapa.html',fraction:0},
    {copy:'Explora el volumen y las posibilidades de tu proyecto.',label:'Simulador 3D ↗',href:'zona3d.html',fraction:.5},
    {copy:'Pon a prueba costos, rendimientos y escenarios adversos.',label:'Abrir laboratorio ↗',href:'laboratorio.html',fraction:.96}
  ];
  const buttons=[...document.querySelectorAll('[data-chapter]')];
  function preferReduced(){return reduced.matches||manualReduced;}
  function applyPreference(){root.dataset.motion=preferReduced()?'reduce':'full';toggle.setAttribute('aria-pressed',String(preferReduced()));toggle.textContent=preferReduced()?'Movimiento reducido':'Reducir movimiento';if(preferReduced())film.pause();}
  applyPreference();reduced.addEventListener('change',applyPreference);
  toggle.addEventListener('click',()=>{
    if(reduced.matches){status.textContent='La reducción de movimiento está activada en tu sistema. Puedes reproducir el video con su botón.';return;}
    manualReduced=!manualReduced;try{localStorage.setItem('bb-motion',manualReduced?'reduce':'full');}catch{}applyPreference();
  });
  function load(){if(!loaded&&film.dataset.src){film.src=film.dataset.src;film.load();loaded=true;}}
  function announceChapter(index,seek){
    active=index;const chapter=chapters[index];buttons.forEach((b,i)=>b.setAttribute('aria-pressed',String(i===index)));
    document.getElementById('territory-chapter-copy').textContent=chapter.copy;
    const link=document.getElementById('territory-chapter-link');link.textContent=chapter.label;link.href=chapter.href;
    if(seek){film.pause();pendingSeek=chapter.fraction;load();applySeek();}
  }
  function applySeek(){if(pendingSeek!==null&&Number.isFinite(film.duration)&&film.duration>0){film.currentTime=Math.min(film.duration-.05,film.duration*pendingSeek);pendingSeek=null;}}
  buttons.forEach((b,index)=>b.addEventListener('click',()=>announceChapter(index,true)));
  film.addEventListener('loadedmetadata',applySeek);
  film.addEventListener('timeupdate',()=>{if(film.paused||!Number.isFinite(film.duration))return;const fraction=film.currentTime/film.duration,index=fraction<.3?0:fraction<.78?1:2;if(index!==active)announceChapter(index,false);});
  play.addEventListener('click',async()=>{if(!film.paused){film.pause();return;}load();if(film.ended)film.currentTime=0;try{await film.play();status.textContent='';}catch{status.textContent='No se pudo reproducir la animación. Las herramientas siguen disponibles.';}});
  film.addEventListener('play',()=>{play.textContent='Pausar';play.setAttribute('aria-label','Pausar transformación arquitectónica');});
  film.addEventListener('pause',()=>{play.textContent=film.ended?'Repetir':'Reproducir';play.setAttribute('aria-label','Reproducir transformación arquitectónica');});
  film.addEventListener('ended',()=>{announceChapter(2,false);play.textContent='Repetir';});
  film.addEventListener('error',()=>{status.textContent='Animación no disponible. Puedes explorar las tres etapas con sus botones.';play.textContent='Reintentar';loaded=false;});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)film.pause();});
  // One automatic pass only, when visible, with no reduced-motion or data-saving preference.
  if('IntersectionObserver' in window){let started=false;
    const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(!entry.isIntersecting){film.pause();continue;}if(started||preferReduced()||navigator.connection?.saveData)continue;started=true;load();film.play().catch(()=>{});}}, {threshold:.45});observer.observe(film);
    window.addEventListener('pagehide',()=>observer.disconnect(),{once:true});
  }
})();
