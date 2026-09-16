/* Pure scenario math. MXN, nominal values; estimates, not market quotations. */
(function(root){
  'use strict';
  function number(n,name,min=0,max=1e12){if(!Number.isFinite(n)||n<min||n>max)throw new Error(name+' está fuera del rango permitido.');return n;}
  function percent(n,name,max=100){return number(n,name,0,max)/100;}
  function payment(principal,annualRate,years){
    if(principal===0)return 0;
    const n=years*12,r=annualRate/12;
    return r===0?principal/n:principal*r/(-Math.expm1(-n*Math.log1p(r)));
  }
  function flip(v){
    const purchase=number(v.purchase,'Precio de compra',1), sale=number(v.sale,'Precio de venta',1);
    const works=number(v.works,'Remodelación'),months=number(v.months,'Plazo',1,120),holding=number(v.holding,'Gasto mensual');
    const closing=percent(v.closing,'Gastos de adquisición',50),commission=percent(v.commission,'Comisión',50),contingency=percent(v.contingency,'Imprevistos',100),target=percent(v.target,'Retorno objetivo',500);
    const acquisition=purchase*closing,renovation=works*(1+contingency),carry=months*holding;
    const cost=purchase+acquisition+renovation+carry,netSale=sale*(1-commission),profit=netSale-cost;
    return {acquisition,renovation,carry,cost,netSale,profit,roi:profit/cost*100,breakEven:cost/(1-commission),maxPurchase:(netSale/(1+target)-renovation-carry)/(1+closing),monthlyProfit:profit/months};
  }
  function rental(v){
    const price=number(v.price,'Precio',1),rent=number(v.rent,'Renta',0),down=percent(v.down,'Enganche'),rate=percent(v.rate,'Tasa anual',60),years=number(v.years,'Plazo del crédito',1,40);
    const vacancy=percent(v.vacancy,'Vacancia'),expenses=number(v.expenses,'Gastos'),closing=percent(v.closing,'Gastos de adquisición',50);
    const debt=payment(price*(1-down),rate,years),income=rent*(1-vacancy),noi=income-expenses,flow=noi-debt,equity=price*(down+closing);
    return {debt,income,noi,flow,equity,cashReturn:equity>0?flow*12/equity*100:null,coverage:debt>0?noi/debt:null,breakEvenOccupancy:rent>0?(expenses+debt)/rent*100:null};
  }
  function stress(v){
    rental(v);
    return [{name:'Base',...rental(v)},{name:'Renta -10%, vacancia +10 pp',...rental({...v,rent:v.rent*.9,vacancy:Math.min(100,v.vacancy+10)})},{name:'Anterior + gastos 20% mayores',...rental({...v,rent:v.rent*.9,vacancy:Math.min(100,v.vacancy+10),expenses:v.expenses*1.2})},{name:'Anterior + tasa 2 pp mayor',...rental({...v,rent:v.rent*.9,vacancy:Math.min(100,v.vacancy+10),expenses:v.expenses*1.2,rate:Math.min(60,v.rate+2)})}];
  }
  function compare(rows){
    if(rows.length<2||rows.length>6)throw new Error('Compara entre 2 y 6 inmuebles.');
    const result=rows.map(r=>({name:String(r.name||'Sin nombre').slice(0,100),price:number(r.price,'Precio',1),area:number(r.area,'Superficie',1),rent:number(r.rent,'Renta'),expenses:number(r.expenses,'Gastos')})).map(r=>({...r,pm2:r.price/r.area,gross:r.rent*12/r.price*100,net:(r.rent-r.expenses)*12/r.price*100}));
    const sorted=result.map(r=>r.pm2).sort((a,b)=>a-b),i=Math.floor(sorted.length/2),median=sorted.length%2?sorted[i]:(sorted[i-1]+sorted[i])/2;
    return {median,rows:result.map(r=>({...r,difference:(r.pm2/median-1)*100}))};
  }
  const api={flip,rental,stress,compare,payment};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.BrickBitLab=api;
})(typeof window!=='undefined'?window:globalThis);
