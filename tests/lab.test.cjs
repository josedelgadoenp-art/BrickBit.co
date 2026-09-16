const {test}=require('node:test');
const assert=require('node:assert/strict');
const m=require('../assets/brickbit-lab-model.js');
const flip={purchase:1800000,sale:2800000,works:300000,contingency:15,closing:6,commission:4,months:8,holding:6000,target:20};
const rent={price:3000000,rent:22000,down:40,rate:10.5,years:20,vacancy:5,expenses:3000,closing:6};
test('flip includes purchase, all captured costs and commission, with target inverse consistency',()=>{
 const r=m.flip(flip);assert.equal(r.cost,2301000);assert.equal(r.netSale,2688000);assert.equal(r.profit,387000);
 const target=m.flip({...flip,purchase:r.maxPurchase});assert.ok(Math.abs(target.roi-20)<1e-9);
 assert.ok(Math.abs(m.flip({...flip,sale:r.breakEven}).profit)<1e-8);
 assert.ok(m.flip({...flip,sale:100000}).maxPurchase<0);
});
test('rental amortizes zero interest and identifies impossible break-even occupancy',()=>{
 assert.equal(m.payment(120000,0,10),1000);
 const cash=m.rental({...rent,down:100});assert.equal(cash.debt,0);assert.equal(cash.coverage,null);assert.equal(cash.income,20900);
 const bad=m.rental({...rent,rent:1000});assert.ok(bad.breakEvenOccupancy>100);assert.ok(bad.flow<0);
 assert.equal(m.rental({...rent,down:0,closing:0}).cashReturn,null);
});
test('stress scenarios accumulate shocks and never improve cashflow',()=>{
 const scenarios=m.stress(rent);for(let i=1;i<scenarios.length;i++)assert.ok(scenarios[i].flow<=scenarios[i-1].flow);
 assert.equal(m.stress({...rent,rate:0,down:100})[3].debt,0);
});
test('comparable median is robust to ordering and yield separates expenses',()=>{
 const a={name:'A',price:1000000,area:100,rent:10000,expenses:2000};
 const r=m.compare([a,{...a,name:'B',price:3000000}]);assert.equal(r.median,20000);assert.equal(r.rows[0].gross,12);assert.equal(r.rows[0].net,9.6);assert.equal(r.rows[0].difference,-50);
});
test('invalid inputs fail instead of generating infinite or misleading results',()=>{
 assert.throws(()=>m.flip({...flip,purchase:NaN}));assert.throws(()=>m.flip({...flip,commission:100}));
 assert.throws(()=>m.rental({...rent,price:0}));assert.throws(()=>m.rental({...rent,vacancy:101}));
 assert.throws(()=>m.compare([{name:'A',area:0,price:1,rent:0,expenses:0},{name:'B',area:1,price:1,rent:0,expenses:0}]));
});
