// Regression checks for station churn and measurement-based freshness.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const data=JSON.parse(fs.readFileSync('site/data/latest.json','utf8'));
const now=Date.parse(data.collected_at),elements=new Map();
class Clock extends Date{static now(){return now;}}
function element(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',addEventListener(){},querySelectorAll(){return[];}});return elements.get(id);}
const context=vm.createContext({console,Intl,Date:Clock,Map,Set,Number,String,Math,document:{querySelector:element},fetch:async()=>({ok:true,json:async()=>data})});
vm.runInContext(fs.readFileSync('site/app.js','utf8'),context);
setImmediate(()=>{
  const at=hours=>new Date(now-hours*3600000).toISOString().replace('.000Z','Z');
  const row=hours=>({time:at(hours),temperature:8,humidity:80,wind:null,precipitation:null});
  const station=(id,distance,status,hours)=>({id,name:id,provider:'openSenseMap',distance,status,url:'https://example.org/'+id,rows:[row(hours)]});
  const location=structuredClone(data.locations[0]);
  location.community.stations=[station('stale-nearest',1,'stale',4),...Array.from({length:12},(_,i)=>station('active-'+i,100+i,'ok',.5)),station('expired',2,'ok',4)];
  context.fixture=location;
  const cards=vm.runInContext('reportingCommunity(fixture)',context);
  assert.deepEqual(Array.from(cards,s=>s.id),['active-0','active-1','active-2']);
  vm.runInContext('renderCommunity(fixture)',context);
  const markup=element('#community').innerHTML;
  assert.equal((markup.match(/class="community-card"/g)||[]).length,3);
  assert.doesNotMatch(markup,/stale-nearest|expired|active-3/);
  const lines=vm.runInContext('communitySeries(fixture,"temperature",Date.now())',context);
  assert.equal(lines.length,3);
  assert.equal(new Set(Array.from(lines,s=>s.color)).size,3);
  assert.match(lines[0].label,/recently seen/);
  assert.equal(location.community.stations.length,14,'UI selection must not mutate retained history');
  context.source={provider:'Météo-France',status:'ok',sources:[],fetched_at:at(0),rows:[row(37)]};
  assert.equal(vm.runInContext('old(source)',context),true,'fresh download must not mask old measurements');
  context.source.rows=[row(35)];
  assert.equal(vm.runInContext('old(source)',context),false);
  context.source.provider='DWD via Bright Sky';context.source.rows=[row(4)];
  assert.equal(vm.runInContext('old(source)',context),true);
  vm.runInContext('renderLocations()',context);
  assert.match(element('#locations').innerHTML,/published daily/);
  assert.match(element('#locations').innerHTML,/h ago/);
  console.log('Community display caps, distinct line colours, retained history and observation-age policies passed.');
});
