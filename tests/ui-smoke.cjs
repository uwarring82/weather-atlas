// Rendering checks across the real dataset; visual browser QA remains separate.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const data=JSON.parse(fs.readFileSync('site/data/latest.json','utf8')),elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',hidden:false,href:'',listeners:{},addEventListener(n,f){this.listeners[n]=f;},querySelectorAll(){return[];}});return elements.get(id);}
const context=vm.createContext({console,Intl,Date,Map,Set,Number,String,Math,document:{querySelector:element},fetch:async()=>({ok:true,json:async()=>data})});
vm.runInContext(fs.readFileSync('site/app.js','utf8'),context);
setImmediate(()=>{
  assert.equal(element('#error').textContent,'');let count=0;
  for(const location of data.locations)for(const mode of ['forecast','observations'])for(const metric of ['temperature','precipitation','wind','humidity'])for(const horizon of [48,168]){
    vm.runInContext(`state.location=${JSON.stringify(location.id)};state.mode=${JSON.stringify(mode)};state.metric=${JSON.stringify(metric)};state.hours=${horizon};render();`,context);
    assert.match(element('#chart').innerHTML,/<svg/);
    assert.doesNotMatch(element('#chart').innerHTML,/NaN|undefined/);
    assert.match(element('#table').innerHTML,/<table/);
    assert.match(element('#providers').innerHTML,/DWD ICON/);
    assert.match(element('#community').innerHTML,/openSenseMap|No recent/);count++;
  }
  console.log(`Rendering smoke check passed for ${count} location/view/metric/horizon combinations.`);
});
