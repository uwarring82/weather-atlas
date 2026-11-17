'use strict';
const $ = (selector) => document.querySelector(selector);
const COLORS = ['#34654d', '#c46a40', '#577ea5', '#917398'];
const METRICS = {temperature: {label:'Temperature', unit:'°C'}, precipitation: {label:'Precipitation',unit:'mm'}, wind: {label:'Wind speed',unit:'km/h'}, humidity: {label:'Relative humidity',unit:'%'}};
const state = {data:null, location:'hasslinghausen', mode:'forecast', metric:'temperature', hours:48};
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const valid = (v) => typeof v === 'number' && Number.isFinite(v);
const value = (v, digits=1) => valid(v) ? v.toLocaleString('en-GB', {maximumFractionDigits:digits,minimumFractionDigits:digits}) : '—';
const date = (v, options={}) => new Intl.DateTimeFormat('en-GB', {timeZone:'Europe/Berlin', day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',...options}).format(new Date(v));
const hour = (v) => new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit'}).format(new Date(v));
const old = (item) => item.status !== 'ok' || !item.fetched_at || Date.now()-Date.parse(item.fetched_at)>(item.stale_after_hours||3)*3600000;
const age = (timestamp) => {
  if (!timestamp) return 'Unavailable';
  const h = Math.max(0, (Date.now()-Date.parse(timestamp))/3600000);
  return h<1 ? `${Math.floor(h*60)} min ago` : h<48 ? `${Math.floor(h)} h ago` : `${Math.floor(h/24)} days ago`;
};
function latestObservation(location) {
  return [...location.observations.rows].reverse().find(r => valid(r.temperature) && Date.parse(r.time)<=Date.now());
}
function renderLocations() {
  $('#locations').innerHTML = state.data.locations.map((l,i) => {
    const r = latestObservation(l);
    const details=[valid(r?.wind)?`${value(r.wind,0)} km/h wind`:null,valid(r?.humidity)?`${value(r.humidity,0)}% humidity`:null].filter(Boolean).join(' · ')||'Wind and humidity not reported';
    return `<button class="location-card" type="button" data-location="${l.id}" aria-pressed="${l.id===state.location}"><span class="number">0${i+1} / ${escapeHTML(l.region)}</span><span class="selected-marker">${l.id===state.location?'● SELECTED':'↗ EXPLORE'}</span><h2>${escapeHTML(l.name)}</h2><span class="street">${escapeHTML(l.street)}</span><div class="card-weather"><div class="temperature">${value(r?.temperature)}<small> °C</small></div><div class="card-meta">${escapeHTML(l.observations.provider||'Official station')} observation<br>${r?escapeHTML(date(r.time)):'No observations available'}<br>${r?details:'Check source status'}</div></div></button>`;
  }).join('');
  const degraded = state.data.locations.some(l => old(l.observations) || l.forecasts.some(old));
  $('#collection-status').innerHTML = `<i class="dot ${degraded?'warn':''}"></i>${degraded?'Some sources delayed · ':''}Collected ${escapeHTML(date(state.data.collected_at))} CET`;
  // Intl supplies the correct abbreviation across daylight saving time.
  $('#collection-status').innerHTML = $('#collection-status').innerHTML.replace(' CET', ` ${new Intl.DateTimeFormat('en',{timeZone:'Europe/Berlin',timeZoneName:'short'}).formatToParts(new Date(state.data.collected_at)).find(p=>p.type==='timeZoneName').value}`);
}
function seriesFor(location) {
  const now = Date.now();
  if (state.mode === 'observations') return [{id:'dwd',label:(location.observations.provider||'Official station')+' observations',color:COLORS[0],rows:location.observations.rows.filter(r=>Date.parse(r.time)>=now-7*86400000 && Date.parse(r.time)<=now)},...(location.community?.stations||[]).filter(s=>s.rows.some(r=>valid(r[state.metric]))).map((s,i)=>({...s,label:`${s.name} · community`,color:[COLORS[1],COLORS[2],COLORS[3],'#a78c48','#739985','#856a58'][i%6],rows:s.rows.filter(r=>Date.parse(r.time)>=now-7*86400000&&Date.parse(r.time)<=now)}))];
  return location.forecasts.map((f,i)=>({...f,label:f.label+(old(f)?' · delayed':''), color:COLORS[i],rows:f.rows.filter(r=>Date.parse(r.time)>=now && Date.parse(r.time)<=now+state.hours*3600000)}));
}
function renderChart(location) {
  const series = seriesFor(location), metric = state.metric, spec = METRICS[metric];
  const allRows = series.flatMap(s=>s.rows), values=allRows.map(r=>r[metric]).filter(valid);
  $('#explore-title').textContent = `${location.name} · ${state.mode==='forecast'?'the weather ahead':'the past seven days'}`;
  $('#horizon').hidden = state.mode !== 'forecast';
  $('#legend').innerHTML = series.map(s=>`<span class="legend-item"><i style="background:${s.color}"></i>${escapeHTML(s.label)}</span>`).join('');
  $('#chart-summary').textContent = `${spec.label} (${spec.unit}) · ${state.mode==='forecast'?`next ${state.hours===48?'48 hours':'7 days'}`:'last 7 days'} · all times Europe/Berlin`;
  $('#chart-note').textContent = state.mode==='observations' ? 'Measured at nearby official stations. Station details below; source may change between hours. Lines break at missing readings. Precipitation is the total for the hour ending at the indicated time.' : 'Forecast samples at each service’s available resolution. Hover over points for values, or inspect the table. Precipitation is the total for the preceding hour; MET Norway’s longer accumulation periods are left blank. Missing values stay blank; lines connect native forecast samples.';
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
  renderLocations();const location=state.data.locations.find(l=>l.id===state.location);renderChart(location);renderSources(location);renderCommunity(location);
}
function renderCommunity(location){
  const community=location.community||{stations:[]};
  $('#community').innerHTML=community.stations.length?community.stations.map(s=>{
    const row=s.rows.at(-1),delayed=s.status!=='ok'||Date.now()-Date.parse(row.time)>2*3600000;
    return `<article class="community-card"><div class="community-heading"><a href="${escapeHTML(s.url)}">${escapeHTML(s.name)} ↗</a><span class="status">${delayed?'delayed':'reporting'}</span></div><p class="fineprint">${escapeHTML(s.provider)} · ${value(s.distance/1000)} km away</p><div class="community-temp">${value(row.temperature)}<small> °C</small></div><p class="fineprint">Humidity ${value(row.humidity,0)}%${row.humidity_time?` · ${escapeHTML(hour(row.humidity_time))}`:''}${valid(row.wind)?`<br>Wind ${value(row.wind)} km/h · gusts ${value(row.wind_gust)} km/h`:''}<br>Measured ${escapeHTML(date(row.time))} · ${escapeHTML(age(row.time))}</p><span class="fineprint">${escapeHTML(s.quality)}</span></article>`;
  }).join(''):'<p class="fineprint">No recent outdoor community readings found within 15 km. Official observations remain available above.</p>';
  $('#community-note').textContent='Community readings depend on sensor placement and maintenance. Only outdoor openSenseMap temperature readings from the last two hours, within −35 to 55 °C, are selected. History builds from hourly collections and appears under Recent observations. '+(community.wunderground_status==='not_configured'?'Weather Underground is not connected.':community.wunderground_status==='configuration_error'?'Weather Underground configuration needs correction.':community.wunderground_status==='unavailable'?'Weather Underground is currently unavailable.':community.wunderground_status==='partial'?'Some Weather Underground stations are unavailable.':'Weather Underground PWS readings are included where configured.')+(community.errors?.length?' '+community.errors.join(' · '):'');
}
$('#locations').addEventListener('click',event=>{const b=event.target.closest('[data-location]');if(b){state.location=b.dataset.location;render();}});
$('#mode-controls').addEventListener('click',event=>{const b=event.target.closest('[data-mode]');if(b){state.mode=b.dataset.mode;for(const x of $('#mode-controls').querySelectorAll('button'))x.setAttribute('aria-pressed',x===b);render();}});
$('#metric-controls').addEventListener('click',event=>{const b=event.target.closest('[data-metric]');if(b){state.metric=b.dataset.metric;for(const x of $('#metric-controls').querySelectorAll('button'))x.setAttribute('aria-pressed',x===b);render();}});
$('#horizon').addEventListener('change',event=>{state.hours=Number(event.target.value);render();});
fetch('data/latest.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}).then(data=>{state.data=data;render();}).catch(error=>{$('#collection-status').textContent='Weather data unavailable';$('#error').hidden=false;$('#error').textContent=`The weather archive could not be loaded (${error.message}). Please reload, or check the repository’s collection workflow.`;});
