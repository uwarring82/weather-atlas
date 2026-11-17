// Exercise map state transitions without requesting tiles or launching a browser.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const data=JSON.parse(fs.readFileSync('site/data/latest.json','utf8')),nodes=new Map(),created=[],fits=[];
function element(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',attributes:{},listeners:{},classList:{add(){},toggle(){}},setAttribute(k,v){this.attributes[k]=v;},addEventListener(k,v){this.listeners[k]=v;},querySelectorAll(){return[];}});return nodes.get(id);}
let pan=null,removed=null;
const map={fitBounds(bounds){fits.push(bounds);return this;},panTo(point){pan=point;return this;},removeLayer(layer){removed=layer;},invalidateSize(){}};
function layer(type,point,options){const item={type,point,options,handlers:{},children:[],on(name,handler){this.handlers[name]=handler;return this;},addTo(parent){parent.children?.push(this);return this;},bindTooltip(){return this;},bindPopup(html){this.popup=html;return this;},getElement(){return {classList:{toggle(){}}};},getLatLng(){return this.point;},openPopup(){this.opened=true;return this;},clearLayers(){this.children=[];}};created.push(item);return item;}
const L={map:()=>map,control:{zoom:()=>layer('zoom'),scale:()=>layer('scale')},tileLayer:(url,opts)=>layer('tiles',url,opts),layerGroup:()=>layer('group'),marker:(point,opts)=>layer('marker',point,opts),polyline:(point,opts)=>layer('line',point,opts),divIcon:opts=>opts,latLngBounds:points=>({points,pad(){return this;}})};
const context=vm.createContext({document:{querySelector:element},L,Intl,Date,Map,Number,String,console});
vm.runInContext(fs.readFileSync('site/map.js','utf8'),context);
const atlas=context.WeatherAtlasMap,options={getStations:l=>l.nearby_stations,onLocationSelect:id=>atlas.render(data,id,options)};
const location=data.locations[0];
atlas.render(data,location.id,options);
assert.equal((element('#map-station-list').innerHTML.match(/class="map-station-row"/g)||[]).length,location.nearby_stations.length);
assert.equal(created.filter(x=>x.type==='marker').length,location.nearby_stations.length+1);
assert.equal(created.find(x=>x.type==='tiles').point,'https://tile.openstreetmap.org/{z}/{x}/{y}.png');
assert.match(created.find(x=>x.type==='tiles').options.attribution,/OpenStreetMap/);
const count=fits.length;
atlas.render(data,location.id,options);
assert.equal(fits.length,count,'Changing other dashboard controls must not reset the map view');
const station=location.nearby_stations[2];
atlas.focusStation(station.provider+':'+station.id);
assert.deepEqual(Array.from(pan),[station.latitude,station.longitude]);
assert.ok(created.some(x=>x.type==='marker'&&x.opened));
assert.ok(element('#map-station-detail').innerHTML.includes(station.name.replace(/&/g,'&amp;')));
element('#map-lines').listeners.click();
assert.equal(element('#map-lines').attributes['aria-pressed'],'false');
assert.ok(removed);
const before=created.filter(x=>x.type==='marker').length;
element('#map-overview').listeners.click();
assert.equal(created.filter(x=>x.type==='marker').length-before,data.locations.reduce((n,l)=>n+l.nearby_stations.length+1,0));
assert.equal(element('#map-overview').attributes['aria-pressed'],'true');
const other=data.locations[1],center=[...created].reverse().find(x=>x.type==='marker'&&x.options.title===other.name);
center.handlers.click();
assert.match(element('#network-title').textContent,new RegExp(other.name));
assert.equal(element('#map-overview').attributes['aria-pressed'],'false');
created.find(x=>x.type==='tiles').handlers.tileerror();
assert.match(element('#map-status').textContent,/could not load/);
console.log('Map markers, popups, distance toggle, overview, place selection and tile-error fallback passed.');
