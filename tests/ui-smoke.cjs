// Rendering checks across the real dataset; visual browser QA remains separate.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const data=JSON.parse(fs.readFileSync('site/data/latest.json','utf8')),elements=new Map();
const markup=fs.readFileSync('site/index.html','utf8');
function element(id){assert.ok(markup.includes(`id="${id.slice(1)}"`),`Missing element ${id}`);if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',hidden:false,href:'',listeners:{},addEventListener(n,f){this.listeners[n]=f;},querySelectorAll(){return[];}});return elements.get(id);}
const context=vm.createContext({console,Intl,Date,Map,Set,Number,String,Math,document:{querySelector:element},fetch:async()=>({ok:true,json:async()=>data})});
vm.runInContext(fs.readFileSync('site/app.js','utf8'),context);
setImmediate(()=>{
  assert.equal(element('#error').textContent,'');let count=0;
  for(const location of data.locations)for(const mode of ['forecast','observations'])for(const metric of ['temperature','precipitation','wind','humidity'])for(const horizon of [48,168]){
    vm.runInContext(`state.location=${JSON.stringify(location.id)};state.mode=${JSON.stringify(mode)};state.metric=${JSON.stringify(metric)};state.hours=${horizon};render();`,context);
    const rows=mode==='observations'?[...location.observations.rows,...(location.community?.stations||[]).flatMap(s=>s.rows)]:location.forecasts.flatMap(s=>s.rows);
    const now=Date.now(),start=mode==='observations'?now-7*86400000:now,end=mode==='observations'?now:now+horizon*3600000;
    const available=rows.some(r=>typeof r[metric]==='number'&&Number.isFinite(r[metric])&&Date.parse(r.time)>=start&&Date.parse(r.time)<=end);
    assert.match(element('#chart').innerHTML,available?/<svg/:/No values available/);
    assert.doesNotMatch(element('#chart').innerHTML,/NaN|undefined/);
    assert.match(element('#table').innerHTML,available?/<table/:/No hourly values available/);
    assert.match(element('#providers').innerHTML,/DWD ICON/);
    assert.match(element('#community').innerHTML,/openSenseMap|No recent/);count++;
  }
  console.log(`Rendering smoke check passed for ${count} location/view/metric/horizon combinations.`);
});
