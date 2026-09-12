/* Motion guides attention and acknowledges real state changes; never alters data. */
(() => {
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const allowed=()=>!reduced.matches&&document.documentElement.dataset.motion!=='reduce';
  const animate=(node,delay=0)=>{if(!node||!allowed()||typeof node.animate!=='function')return;node.getAnimations?.().forEach(a=>a.cancel());node.animate([{opacity:.25,transform:'translateY(10px)'},{opacity:1,transform:'translateY(0)'}],{duration:420,delay,easing:'cubic-bezier(.16,1,.3,1)'});};
  if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>{
    let i=0;entries.forEach(e=>{if(e.isIntersecting){animate(e.target,Math.min(i++*45,180));observer.unobserve(e.target);}});
  },{threshold:.1});document.querySelectorAll('.lab-feature,.methodology,.tool-card').forEach(e=>observer.observe(e));window.addEventListener('pagehide',()=>observer.disconnect(),{once:true});}
  document.querySelectorAll('[data-tool-filter]').forEach(button=>button.addEventListener('click',()=>{
    document.querySelectorAll('[data-tool-filter]').forEach(b=>b.setAttribute('aria-pressed',b===button));let count=0;
    document.querySelectorAll('.tool-card').forEach(card=>{const show=button.dataset.toolFilter==='all'||card.querySelector('.tool-category').textContent===button.dataset.toolFilter;card.hidden=!show;if(show){animate(card,Math.min(count*35,140));count++;}});
    document.getElementById('tool-filter-status').textContent=count+' herramientas disponibles';
  }));
  document.querySelectorAll('[data-h]').forEach(b=>b.addEventListener('click',()=>{animate(document.getElementById('chart-line'));animate(document.getElementById('exp-growth'),35);}));
  document.getElementById('exp-city')?.addEventListener('change',()=>animate(document.querySelector('.chart-wrap')));
  document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>animate(document.getElementById('panel-'+b.dataset.tab))));
  document.querySelectorAll('.lab-panel form').forEach(f=>f.addEventListener('submit',()=>animate(document.getElementById(f.id.replace('-form','-results')))));
  reduced.addEventListener('change',()=>{if(reduced.matches)document.getAnimations?.().forEach(a=>a.cancel());});
})();
