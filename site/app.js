'use strict';
const $ = (selector) => document.querySelector(selector);
const COLORS = ['#34654d', '#c46a40', '#577ea5', '#917398'];
const MONITOR_COLORS = ['#c46a40','#577ea5','#917398','#a4862d','#378a8b','#ad5975','#6554a4'];
const MAX_STATIONS = 7;
const ICONS={temperature:'<path d="M10 14.8V5a2 2 0 0 1 4 0v9.8a4 4 0 1 1-4 0Z"/><path d="M12 10v8M16 6h3M16 10h2"/>',humidity:'<path d="M12 3S5 10 5 15a7 7 0 0 0 14 0c0-5-7-12-7-12Z"/><path d="m9 17 6-6M9 11h.01M15 17h.01"/>',wind:'<path d="M3 8h12a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h6a3 3 0 1 1-3 3"/>',precipitation:'<path d="M7 14H6a4 4 0 0 1 0-8 6 6 0 0 1 11-1 4.5 4.5 0 0 1 1 9h-1M8 17l-1 3M12 16l-1 3M16 17l-1 3"/>'};
const glyph=metric=>`<svg class="metric-glyph" viewBox="0 0 24 24" aria-hidden="true">${ICONS[metric]}</svg>`;
const METRICS = {temperature: {label:'Temperature', unit:'°C'}, precipitation: {label:'Precipitation',unit:'mm'}, wind: {label:'Wind speed',unit:'km/h'}, humidity: {label:'Relative humidity',unit:'%'}};
const state = {data:null, location:'hasslinghausen', mode:'forecast', metric:'temperature', hours:48};
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const valid = (v) => typeof v === 'number' && Number.isFinite(v);
const value = (v, digits=1) => valid(v) ? v.toLocaleString('en-GB', {maximumFractionDigits:digits,minimumFractionDigits:digits}) : '—';
const date = (v, options={}) => new Intl.DateTimeFormat('en-GB', {timeZone:'Europe/Berlin', day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',...options}).format(new Date(v));
const hour = (v) => new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit'}).format(new Date(v));
const old = (item) => {
  if(item.status!=='ok')return true;
  if(Array.isArray(item.sources)){
    const measured=[...item.rows].reverse().find(r=>valid(r.temperature)&&Date.parse(r.time)<=Date.now());
    const limit=item.provider==='Météo-France'?36:3;
    return !measured||Date.now()-Date.parse(measured.time)>limit*3600000;
  }
  return !item.fetched_at||Date.now()-Date.parse(item.fetched_at)>3*3600000;
};
const age = (timestamp) => {
  if (!timestamp) return 'Unavailable';
  const h = Math.max(0, (Date.now()-Date.parse(timestamp))/3600000);
  return h<1 ? `${Math.floor(h*60)} min ago` : h<48 ? `${Math.floor(h)} h ago` : `${Math.floor(h/24)} days ago`;
};
function latestObservation(location) {
  return [...location.observations.rows].reverse().find(r => valid(r.temperature) && Date.parse(r.time)<=Date.now());
}
function temperatureTrace(location){
  const end=Date.now(),start=end-24*3600000,rows=location.observations.rows.filter(r=>Date.parse(r.time)>=start&&Date.parse(r.time)<=end&&valid(r.temperature));
  if(!rows.length)return '';
  const min=Math.min(...rows.map(r=>r.temperature)),max=Math.max(...rows.map(r=>r.temperature)),range=Math.max(1,max-min);
  let path='',previous=null;
  for(const row of rows){const t=Date.parse(row.time),x=2+(t-start)/(end-start)*296,y=35-(row.temperature-min)/range*30;path+=`${previous===null||t-previous>1.5*3600000?'M':'L'}${x.toFixed(1)},${y.toFixed(1)} `;previous=t;}
  return `<svg class="card-spark" viewBox="0 0 300 40" role="img" aria-label="Observed temperature over the last 24 hours"><path d="${path}"/></svg><span class="spark-caption"><span>LAST 24H · STATION RECORD</span><span>${value(min)}–${value(max)}°</span></span>`;
}
function renderSnapshot(location){
  const row=latestObservation(location),specs=[['temperature','Station temperature','°C'],['precipitation','Last-hour precipitation','mm'],['wind','Wind at the station','km/h'],['humidity','Relative humidity','%']];
  $('#weather-snapshot').innerHTML=specs.map(([metric,label,unit])=>{
    const v=row?.[metric],meter=metric==='humidity'&&valid(v)?`<div class="metric-meter"><span style="width:${Math.max(0,Math.min(100,v))}%"></span></div>`:'';
    return `<article class="snapshot-card"><div class="snapshot-top"><span>${label}</span>${glyph(metric)}</div><div class="snapshot-value">${value(v)} <small>${unit}</small></div><p class="snapshot-note">${valid(v)&&row?`${escapeHTML(date(row.time))} · ${escapeHTML(age(row.time))}`:'Not reported by this station'}<br>${escapeHTML(location.observations.provider||'Official station')}${location.observations.provider==='Météo-France'?' · published daily':''}</p>${meter}</article>`;
  }).join('');
}
function renderOutlook(location){
  const start=Math.ceil(Date.now()/3600000)*3600000,cards=[];
  for(let i=0;i<8;i++){
    const t=start+i*6*3600000;
    const samples=location.forecasts.map(f=>f.rows.find(r=>Date.parse(r.time)===t)).filter(Boolean);
    const temps=samples.map(r=>r.temperature).filter(valid),rain=samples.map(r=>r.precipitation).filter(valid);
    cards.push({t,min:temps.length?Math.min(...temps):null,max:temps.length?Math.max(...temps):null,rainMin:rain.length?Math.min(...rain):null,rainMax:rain.length?Math.max(...rain):null,count:temps.length});
  }
  const all=cards.flatMap(c=>[c.min,c.max]).filter(valid),lo=all.length?Math.min(...all)-1:0,hi=all.length?Math.max(...all)+1:1;
  const range=(a,b,unit)=>valid(a)?`${value(a)}${a!==b?'–'+value(b):''}${unit}`:'—';
  $('#forecast-strip').innerHTML=cards.map(c=>`<article class="outlook-card"><p class="outlook-date">${escapeHTML(date(c.t,{hour:undefined,minute:undefined}))}</p><h3>${escapeHTML(hour(c.t))}</h3>${glyph('temperature')}<p class="outlook-temp">${range(c.min,c.max,'°')}</p><div class="outlook-range">${valid(c.min)?`<span style="left:${(c.min-lo)/(hi-lo)*100}%;width:${Math.max(3,(c.max-c.min)/(hi-lo)*100)}%"></span>`:''}</div><p class="outlook-rain" title="Precipitation during the preceding hour">${glyph('precipitation')}${range(c.rainMin,c.rainMax,' mm')}</p><p class="outlook-sources">${c.count} forecasts</p></article>`).join('');
}
function reportingStations(location){
  return [...(location.nearby_stations||location.community?.stations||[])].filter(s=>{
    const row=s.rows.at(-1),time=Date.parse(row?.time);
    return s.status==='ok'&&valid(row?.temperature)&&time<=Date.now()&&Date.now()-time<=(s.observation_stale_after_hours||2)*3600000;
  }).sort((a,b)=>a.distance-b.distance).slice(0,MAX_STATIONS);
}
function monitorSeries(location,metric,now){
  const primaryIds=new Set(location.observations.sources.map(s=>String(s.station_id||s.dwd_station_id||s.id)));
  const candidates=[...(location.nearby_stations||[]),...(location.observations.nearby_stations||[]),...(location.community?.stations||[])];
  const unique=[...new Map(candidates.filter(s=>!(s.official&&primaryIds.has(String(s.id)))).map(s=>[s.provider+':'+s.id,s])).values()];
  return unique.map(s=>({...s,rows:s.rows.filter(r=>Date.parse(r.time)>=now-7*86400000&&Date.parse(r.time)<=now)}))
    .filter(s=>s.rows.some(r=>valid(r[metric]))).sort((a,b)=>a.distance-b.distance).slice(0,MAX_STATIONS)
    .map((s,i)=>({...s,label:`${s.name} · ${s.status==='stale'?'recently seen':s.provider}`,color:MONITOR_COLORS[i]}));
}

function renderLocations() {
  $('#locations').innerHTML = state.data.locations.map((l,i) => {
    const r = latestObservation(l);
    const details=[valid(r?.wind)?`${value(r.wind,0)} km/h wind`:null,valid(r?.humidity)?`${value(r.humidity,0)}% humidity`:null].filter(Boolean).join(' · ')||'Wind and humidity not reported';
    return `<button class="location-card" type="button" data-location="${l.id}" aria-pressed="${l.id===state.location}"><span class="number">0${i+1} / ${escapeHTML(l.region)}</span><span class="selected-marker">${l.id===state.location?'● SELECTED':'↗ EXPLORE'}</span><h2>${escapeHTML(l.name)}</h2><span class="street">${escapeHTML(l.street)}</span><div class="card-weather"><div class="temperature">${value(r?.temperature)}<small> °C</small></div><div class="card-meta">${escapeHTML(l.observations.provider||'Official station')} observation<br>${r?escapeHTML(date(r.time)):'No observations available'}<br>${r?`${old(l.observations)?'Delayed · ':''}${escapeHTML(age(r.time))}${l.observations.provider==='Météo-France'?' · published daily':''}`:''}<br>${r?details:'Check source status'}</div></div>${temperatureTrace(l)}</button>`;
  }).join('');
  const degraded = state.data.locations.some(l => old(l.observations) || l.forecasts.some(old));
  $('#collection-status').innerHTML = `<i class="dot ${degraded?'warn':''}"></i>${degraded?'Some sources delayed · ':''}Collected ${escapeHTML(date(state.data.collected_at))} CET`;
  // Intl supplies the correct abbreviation across daylight saving time.
  $('#collection-status').innerHTML = $('#collection-status').innerHTML.replace(' CET', ` ${new Intl.DateTimeFormat('en',{timeZone:'Europe/Berlin',timeZoneName:'short'}).formatToParts(new Date(state.data.collected_at)).find(p=>p.type==='timeZoneName').value}`);
}
function seriesFor(location) {
  const now = Date.now();
  if (state.mode === 'observations') return [{id:'dwd',label:(location.observations.provider||'Official station')+' observations',color:COLORS[0],rows:location.observations.rows.filter(r=>Date.parse(r.time)>=now-7*86400000 && Date.parse(r.time)<=now)},...monitorSeries(location,state.metric,now)];
  return location.forecasts.map((f,i)=>({...f,label:f.label+(old(f)?' · delayed':''), color:COLORS[i],rows:f.rows.filter(r=>Date.parse(r.time)>=now && Date.parse(r.time)<=now+state.hours*3600000)}));
}
function renderChart(location) {
  const series = seriesFor(location), metric = state.metric, spec = METRICS[metric];
  const allRows = series.flatMap(s=>s.rows), values=allRows.map(r=>r[metric]).filter(valid);
  $('#explore-title').textContent = `${location.name} · ${state.mode==='forecast'?'the weather ahead':'the past seven days'}`;
  $('#horizon').hidden = state.mode !== 'forecast';
  $('#legend').innerHTML = series.map(s=>`<span class="legend-item"><i style="background:${s.color}"></i>${escapeHTML(s.label)}</span>`).join('');
  $('#chart-summary').textContent = `${spec.label} (${spec.unit}) · ${state.mode==='forecast'?`next ${state.hours===48?'48 hours':'7 days'}`:'last 7 days'} · all times Europe/Berlin`;
  $('#chart-note').textContent = state.mode==='observations' ? 'Primary official observations plus up to seven nearby monitors with values for this metric in the last seven days. Recently seen stations may no longer be reporting. Full retained history is in the data download. Lines break at missing readings. Precipitation is the total for the hour ending at the indicated time.' : 'Forecast samples at each service’s available resolution. Hover over points for values, or inspect the table. Precipitation is the total for the preceding hour; MET Norway’s longer accumulation periods are left blank. Missing values stay blank; lines connect native forecast samples.';
  if (!values.length) {
    $('#chart').innerHTML = '<p class="empty">No values available for this metric and time range.</p>';
    $('#table').innerHTML = '<p>No hourly values available.</p>';
    return;
  }
  const W=1000,H=280,p={l:47,r:12,t:20,b:37};
  let min=Math.min(...values),max=Math.max(...values),pad=Math.max((max-min)*.15,metric==='temperature'?1:metric==='precipitation'?.3:2);
  min=metric==='temperature'?min-pad:Math.max(0,min-pad); max+=pad;
  if(metric==='humidity')max=Math.min(100,max);
  const times=allRows.map(r=>Date.parse(r.time)), t0=Math.min(...times),t1=Math.max(...times,t0+3600000);
  const x=t=>p.l+(t-t0)/(t1-t0)*(W-p.l-p.r),y=v=>H-p.b-(v-min)/(max-min)*(H-p.t-p.b);
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeHTML(spec.label)} for ${escapeHTML(location.name)}"><title>${escapeHTML(spec.label)} comparison, ${escapeHTML(location.name)}</title>`;
  for(let i=0;i<=4;i++){
    const v=min+(max-min)*i/4,py=y(v);
    svg+=`<line class="grid" x1="${p.l}" x2="${W-p.r}" y1="${py}" y2="${py}"/><text x="${p.l-10}" y="${py+4}" text-anchor="end">${value(v, metric==='precipitation'?1:0)}</text>`;
  }
  for(let i=0;i<=6;i++){
    const t=t0+(t1-t0)*i/6;
    svg+=`<text x="${x(t)}" y="${H-12}" text-anchor="${i===0?'start':i===6?'end':'middle'}">${escapeHTML(state.hours===48&&state.mode==='forecast'?date(t,{month:undefined}):date(t,{hour:undefined,minute:undefined}))}</text>`;
  }
  for(const s of series){
    let path='',connected=false,previous=null;
    for(const row of s.rows){
      const t=Date.parse(row.time),v=row[metric];
      if(!valid(v)){connected=false;continue;}
      const gap=previous!==null&&t-previous>1.5*3600000;
      // Connect native forecast samples; do not bridge missing hourly observations or rain.
      const move=!connected || (gap && (metric==='precipitation'||state.mode==='observations'));
      path+=`${move?'M':'L'}${x(t).toFixed(2)},${y(v).toFixed(2)} `;connected=true;previous=t;
    }
    svg+=`<path class="series" d="${path}" stroke="${s.color}"/>`;
    for(const row of s.rows.filter(r=>valid(r[metric]))){
      svg+=`<circle cx="${x(Date.parse(row.time))}" cy="${y(row[metric])}" r="4" fill="${s.color}" fill-opacity="${s.rows.length===1?'0.8':'0.01'}"><title>${escapeHTML(s.label)} · ${escapeHTML(date(row.time))}: ${value(row[metric])} ${spec.unit}</title></circle>`;
    }
  }
  svg+='</svg>';$('#chart').innerHTML=svg;
  const timestamps=[...new Set(allRows.map(r=>r.time))].sort();
  const lookup=series.map(s=>new Map(s.rows.map(r=>[r.time,r])));
  $('#table').innerHTML=`<table><caption>${escapeHTML(spec.label)} (${spec.unit}), Europe/Berlin</caption><thead><tr><th scope="col">Time</th>${series.map(s=>`<th scope="col">${escapeHTML(s.label)}</th>`).join('')}</tr></thead><tbody>${timestamps.map(t=>`<tr><th scope="row">${escapeHTML(date(t))}</th>${lookup.map(m=>`<td>${value(m.get(t)?.[metric])}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function renderSources(location){
  const now=Date.now(),end=now+86400000;
  $('#providers').innerHTML=location.forecasts.map((f,i)=>{
    const rows=f.rows.filter(r=>Date.parse(r.time)>=now&&Date.parse(r.time)<=end),temps=rows.map(r=>r.temperature).filter(valid),rain=rows.map(r=>r.precipitation).filter(valid);
    const completeRain=rows.length===24&&rain.length===24;
    return `<article class="provider"><div class="provider-id"><h3><i style="background:${COLORS[i]}"></i>${escapeHTML(f.label)}</h3><span class="status">${old(f)?f.status==='unavailable'?'unavailable':'delayed':'available'}</span></div><div class="range">${temps.length?`${value(Math.min(...temps))}–${value(Math.max(...temps))}°`:'—'}</div><p>Temperature range · next 24h</p><p>${completeRain?`${value(rain.reduce((a,b)=>a+b,0))} mm precipitation`:'24h precipitation total incomplete'}</p><p>${escapeHTML(f.provider||'Source unavailable')}${f.id==='met_no'?' · ECMWF based':''}</p><div class="fetched">Retrieved ${escapeHTML(age(f.fetched_at))}${f.issued_at?`<br>Provider update ${escapeHTML(date(f.issued_at))}`:'<br>Model issue time not supplied'}</div></article>`;
  }).join('');
  const obs=location.observations,latest=latestObservation(location),currentSource=obs.sources.find(s=>s.id===latest?.source_id);
  const distinct=[...new Map(obs.sources.map(s=>[s.station_id||s.dwd_station_id,s])).values()];
  $('#station-info').innerHTML=`<p>${latest?`Latest measurement: <strong>${escapeHTML(date(latest.time))}</strong> (${escapeHTML(age(latest.time))}).`:'No station measurements available.'} ${old(obs)?'Observation collection is delayed.':''} ${obs.publication_note?escapeHTML(obs.publication_note):''}</p><ul class="station-list">${distinct.map(s=>`<li>${escapeHTML(s.station_name)} · ${escapeHTML(s.provider||'DWD')} ${escapeHTML(s.station_id||s.dwd_station_id)} · ${value(s.distance/1000)} km away · ${value(s.height,0)} m elevation</li>`).join('')}</ul>${currentSource?`<p>Latest source: ${escapeHTML(currentSource.station_name)}. Distances and station metadata come from the observation source; metadata can differ between historical and current records.</p>`:''}`;
  $('#map-link').href=`https://www.openstreetmap.org/?mlat=${location.latitude}&mlon=${location.longitude}#map=16/${location.latitude}/${location.longitude}`;
}
function render(){
  renderLocations();const location=state.data.locations.find(l=>l.id===state.location);renderChart(location);renderSources(location);renderCommunity(location);renderSnapshot(location);renderOutlook(location);
  $('#hero-network').textContent=`${state.data.locations.length} places · ${state.data.locations.reduce((n,l)=>n+reportingStations(l).length,0)} monitoring stations · 4 forecasts`;
  globalThis.WeatherAtlasMap?.render(state.data,state.location,{getStations:reportingStations,onLocationSelect:id=>{state.location=id;render();}});
}
function renderCommunity(location){
  const community=location.community||{stations:[]};
  const reporting=reportingStations(location);
  $('#community').innerHTML=reporting.length?reporting.map(s=>{
    const row=s.rows.at(-1);
    return `<article class="community-card"><div class="community-heading"><a href="${escapeHTML(s.url)}">${escapeHTML(s.name)} ↗</a><span class="status">${s.provider==='Météo-France'?'daily':s.official?'official':'reporting'}</span></div><p class="fineprint">${escapeHTML(s.provider)} · ${value(s.distance/1000)} km · straight line</p><div class="community-temp">${value(row.temperature)}<small> °C</small></div><p class="fineprint">${valid(row.humidity)?`Humidity ${value(row.humidity,0)}%`:'Humidity not reported'}${row.humidity_time?` · ${escapeHTML(hour(row.humidity_time))}`:''}${valid(row.wind)?`<br>Wind ${value(row.wind)} km/h${valid(row.wind_gust)?` · gusts ${value(row.wind_gust)} km/h`:''}`:''}<br>Measured ${escapeHTML(date(row.time))} · ${escapeHTML(age(row.time))}</p><span class="fineprint">${escapeHTML(s.quality)}</span><button class="locate-monitor" type="button" data-map-key="${escapeHTML(s.provider+':'+s.id)}">Locate on the map ↗</button></article>`;
  }).join(''):'<p class="fineprint">No recent nearby monitor readings are available. Check the official observations above.</p>';
  $('#community-note').textContent='Showing up to seven nearest reporting monitors, with straight-line distances from the selected street or village centre. Community sensors are searched within 15 km; official French stations within 50 km. Community readings must be less than two hours old; daily French observations may be up to 36 hours old. Coordinates can be approximate. Full retained history and a station-distance CSV are available to download. '+(community.wunderground_status==='not_configured'?'Weather Underground is not connected.':community.wunderground_status==='configuration_error'?'Weather Underground configuration needs correction.':community.wunderground_status==='unavailable'?'Weather Underground is currently unavailable.':community.wunderground_status==='partial'?'Some Weather Underground stations are unavailable.':'Weather Underground PWS readings are included where configured.')+(community.errors?.length?' '+community.errors.join(' · '):'');
}
$('#locations').addEventListener('click',event=>{const b=event.target.closest('[data-location]');if(b){state.location=b.dataset.location;render();}});
$('#mode-controls').addEventListener('click',event=>{const b=event.target.closest('[data-mode]');if(b){state.mode=b.dataset.mode;for(const x of $('#mode-controls').querySelectorAll('button'))x.setAttribute('aria-pressed',x===b);render();}});
$('#metric-controls').addEventListener('click',event=>{const b=event.target.closest('[data-metric]');if(b){state.metric=b.dataset.metric;for(const x of $('#metric-controls').querySelectorAll('button'))x.setAttribute('aria-pressed',x===b);render();}});
$('#horizon').addEventListener('change',event=>{state.hours=Number(event.target.value);render();});
fetch('data/latest.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}).then(data=>{state.data=data;render();}).catch(error=>{$('#collection-status').textContent='Weather data unavailable';$('#error').hidden=false;$('#error').textContent=`The weather archive could not be loaded (${error.message}). Please reload, or check the repository’s collection workflow.`;});

$('#community').addEventListener('click',event=>{const button=event.target.closest('[data-map-key]');if(button){globalThis.WeatherAtlasMap?.focusStation(button.dataset.mapKey);$('#station-network').scrollIntoView?.({behavior:'smooth',block:'start'});}});
