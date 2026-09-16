(() => {
  'use strict';
  const $ = id => document.getElementById(id), model = window.BrickBitLab, key = 'bb-laboratorio-v1';
  const money = n => Number.isFinite(n) ? new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN',maximumFractionDigits:0}).format(n) : 'No aplica';
  const pct = n => Number.isFinite(n) ? n.toFixed(1)+'%' : 'No aplica';
  function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e;}
  const defaults=[{name:'Departamento A',price:2800000,area:95,rent:17500,expenses:2500},{name:'Departamento B',price:3150000,area:110,rent:19500,expenses:3100},{name:'Departamento C',price:2600000,area:82,rent:16800,expenses:2300}];
  let selected='flip';
  function readForm(id){return Object.fromEntries([...$(id).querySelectorAll('input[name]')].map(i=>[i.name,i.value.trim()===''?NaN:Number(i.value)]));}
  function readProperties(){return [...$('compare-inputs').children].map(card=>Object.fromEntries([...card.querySelectorAll('input')].map(i=>[i.name,i.type==='number'?(i.value.trim()===''?NaN:Number(i.value)):i.value])));}
  function propertyInputs(rows){
    $('compare-inputs').replaceChildren();
    rows.forEach((row,index)=>{
      const card=el('fieldset','property-input'),legend=el('legend','',`Inmueble ${index+1}`);card.append(legend);
      [['name','Referencia','text'],['price','Precio de compra (MXN)','number'],['area','Superficie (m²)','number'],['rent','Renta mensual (MXN)','number'],['expenses','Gastos mensuales (MXN)','number']].forEach(([name,label,type])=>{
        const wrap=el('div','lab-field'),lab=el('label','',label),input=el('input');input.id=`property-${index}-${name}`;lab.htmlFor=input.id;input.name=name;input.type=type;input.value=row[name]??'';input.required=true;
        if(type==='number'){input.min=['price','area'].includes(name)?'1':'0';input.max='1000000000';input.step='any';input.inputMode='decimal';}else input.maxLength=100;
        wrap.append(lab,input);card.append(wrap);
      });
      const remove=el('button','text-btn','Quitar inmueble');remove.type='button';remove.disabled=rows.length<=2;remove.setAttribute('aria-label',`Quitar inmueble ${index+1}`);
      remove.addEventListener('click',()=>{const current=readProperties();current.splice(index,1);propertyInputs(current);runCompare();});card.append(remove);$('compare-inputs').append(card);
    });
    $('add-property').disabled=rows.length>=6;
  }
  function metric(label,value,note){const item=el('div','lab-metric');item.append(el('p','metric-label',label),el('strong','metric-value estimate',value));if(note)item.append(el('p','metric-note',note));return item;}
  function table(headers,rows,caption){const wrap=el('div','table-scroll'),table=el('table','lab-table');table.append(el('caption','sr-only',caption));const head=el('thead'),tr=el('tr');headers.forEach(h=>{const cell=el('th','',h);cell.scope='col';tr.append(cell);});head.append(tr);table.append(head);const body=el('tbody');rows.forEach(row=>{const tr=el('tr');row.forEach((v,i)=>{const cell=el(i?'td':'th','',v);if(!i)cell.scope='row';tr.append(cell);});body.append(tr);});table.append(body);wrap.append(table);return wrap;}
  function showError(kind,error){$(kind+'-error').textContent=error.message;$(kind+'-results').replaceChildren(el('p','lab-error','Revisa los campos para calcular un nuevo resultado.'));}
  function runFlip(){try{
    const v=readForm('flip-form'),r=model.flip(v),out=$('flip-results');$('flip-error').textContent='';out.replaceChildren();
    out.append(metric('Utilidad estimada antes de impuestos',money(r.profit),`Retorno de ${pct(r.roi)} durante ${v.months} meses`));
    out.append(el('p','scenario-verdict',r.profit<0?'Con estos supuestos, la operación pierde capital.':r.roi<v.target?'El margen es positivo, pero no alcanza tu retorno objetivo.':'El escenario alcanza tu retorno objetivo. Verifica precio de salida y costos.'));
    const grid=el('div','result-pair');grid.append(metric('Inversión total',money(r.cost)),metric('Venta de equilibrio',money(r.breakEven)));out.append(grid);
    out.append(table(['Concepto','MXN'],[['Compra',money(v.purchase)],['Adquisición',money(r.acquisition)],['Obra + imprevistos',money(r.renovation)],['Tenencia',money(r.carry)],['Venta neta de comisión',money(r.netSale)]],'Desglose de la operación'));
    out.append(metric('Compra máxima para tu objetivo',r.maxPurchase>0?money(r.maxPurchase):'Sin precio viable',r.maxPurchase>0?`Para obtener ${pct(v.target)} sobre toda la inversión.`:'La venta esperada no cubre los otros costos y el retorno objetivo.'));
    return true;
  }catch(e){showError('flip',e);return false;}}
  function runStress(){try{
    const v=readForm('stress-form'),rows=model.stress(v),base=rows[0],out=$('stress-results');$('stress-error').textContent='';out.replaceChildren();
    out.append(metric('Flujo mensual estimado',money(base.flow),'Después de vacancia, gastos y crédito; antes de impuestos.'));
    const grid=el('div','result-pair');grid.append(metric('Cuota mensual',money(base.debt)),metric('Capital inicial',money(base.equity)));out.append(grid);
    out.append(table(['Escenario','Flujo / mes','Cobertura'],rows.map(r=>[r.name,money(r.flow),r.coverage==null?'Sin deuda':r.coverage.toFixed(2)+'×']),'Flujo y cobertura de deuda por escenario'));
    out.append(metric('Ocupación de equilibrio',pct(base.breakEvenOccupancy),base.breakEvenOccupancy>100?'La renta no cubre gastos y deuda incluso con ocupación completa.':'Porcentaje del año ocupado necesario para cubrir gastos y crédito.'));
    out.append(el('p','metric-note','Retorno anual de flujo sobre capital inicial: '+pct(base.cashReturn)+'. No incluye apreciación.'));return true;
  }catch(e){showError('stress',e);return false;}}
  function runCompare(){try{
    const result=model.compare(readProperties()),out=$('compare-results');$('compare-error').textContent='';out.replaceChildren();
    out.append(metric('Mediana de los comparables ingresados',money(result.median)+' / m²','Referencia de tu muestra, no estimación del valor de mercado.'));
    out.append(table(['Inmueble','Precio / m²','Vs. mediana','Rend. bruto','Rend. operativo'],result.rows.map(r=>[r.name,money(r.pm2),pct(r.difference),pct(r.gross),pct(r.net)]),'Comparación de precio y rendimiento de los inmuebles ingresados'));return true;
  }catch(e){showError('compare',e);return false;}}
  const runners={flip:runFlip,compare:runCompare,stress:runStress};
  function selectTab(name,focus=false){selected=name;document.querySelectorAll('[data-tab]').forEach(b=>{const active=b.dataset.tab===name;b.setAttribute('aria-selected',active);b.tabIndex=active?0:-1;$('panel-'+b.dataset.tab).hidden=!active;if(active&&focus)b.focus();});}
  document.querySelectorAll('[data-tab]').forEach(b=>{
    b.addEventListener('click',()=>selectTab(b.dataset.tab));
    b.addEventListener('keydown',e=>{const order=['flip','compare','stress'],index=order.indexOf(selected);let next;
      if(e.key==='ArrowRight')next=order[(index+1)%3];if(e.key==='ArrowLeft')next=order[(index+2)%3];if(e.key==='Home')next=order[0];if(e.key==='End')next=order[2];
      if(next){e.preventDefault();selectTab(next,true);}
    });
  });
  for(const kind of ['flip','stress','compare'])$(kind+'-form').addEventListener('submit',e=>{e.preventDefault();runners[kind]();});
  document.querySelectorAll('.lab-panel form').forEach(form=>form.addEventListener('input',()=>{const output=$(form.id.replace('-form','-results'));output.replaceChildren(el('p','pending-result','Hay cambios sin calcular. Actualiza el escenario para ver el resultado.'));}));
  $('add-property').addEventListener('click',()=>{const rows=readProperties();if(rows.length<6){rows.push({name:'Nuevo inmueble',price:'',area:'',rent:'',expenses:0});propertyInputs(rows);$('compare-results').replaceChildren(el('p','pending-result','Completa el nuevo inmueble y compara de nuevo.'));}});
  function snapshot(){const flip=readForm('flip-form'),stress=readForm('stress-form'),properties=readProperties();model.flip(flip);model.stress(stress);model.compare(properties);return {version:1,savedAt:new Date().toISOString(),flip,stress,properties};}
  $('lab-save').addEventListener('click',()=>{try{const data=snapshot();localStorage.setItem(key,JSON.stringify(data));$('lab-save-status').textContent='Escenarios guardados en este equipo. No se sincronizan con tu cuenta.';}catch(e){$('lab-save-status').textContent='No se guardó: revisa todos los campos o permite el almacenamiento del navegador.';}});
  $('lab-export').addEventListener('click',()=>{try{const data=snapshot(),url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=el('a');a.href=url;a.download='brickbit-escenarios.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);$('lab-save-status').textContent='Archivo exportado con los supuestos de las tres herramientas.';}catch(e){$('lab-save-status').textContent='Completa los campos de las tres herramientas antes de exportar.';}});
  $('lab-print').addEventListener('click',()=>{if(runners[selected]())window.print();});
  $('lab-clear').addEventListener('click',()=>{try{localStorage.removeItem(key);$('lab-save-status').textContent='Copia local borrada. Los campos abiertos se conservan hasta cerrar esta página.';}catch{$('lab-save-status').textContent='El navegador no permitió borrar la copia local.';}});
  let rows=defaults;
  try{const raw=localStorage.getItem(key);if(raw){const data=JSON.parse(raw);if(data.version!==1)throw Error();model.flip(data.flip);model.stress(data.stress);model.compare(data.properties);for(const kind of ['flip','stress'])for(const input of $(kind+'-form').querySelectorAll('input[name]'))input.value=data[kind][input.name];rows=data.properties;$('lab-save-status').textContent='Copia de este equipo recuperada. Revisa que los supuestos sigan vigentes.';}}
  catch{$('lab-save-status').textContent='No se pudo recuperar una copia válida. Se muestran ejemplos editables.';}
  propertyInputs(rows);runFlip();runStress();runCompare();
})();
