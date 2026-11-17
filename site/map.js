/* Leaflet station map. Map tiles load in the browser with normal HTTP caching. */
globalThis.WeatherAtlasMap = (() => {
  const $=id=>document.querySelector(id), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>typeof v==='number'&&Number.isFinite(v)?v.toLocaleString('en-GB',{maximumFractionDigits:1}):'—';
  const date=t=>new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Berlin',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(t));
  const key=s=>s.provider+':'+s.id, coordinates=s=>Number.isFinite(s.latitude)&&Number.isFinite(s.longitude);
  let map,overlay,lines,data,locationId,options={},lastKey='',overview=false,showLines=true,selectedKey=null;
  let markers=new Map(),current=[],tileFailed=false;
  function ensure(){
    if(map)return true;
    if(!globalThis.L){$('#map-status').textContent='Map unavailable. Station coordinates and distances remain available in the download.';return false;}
    map=L.map('station-map',{scrollWheelZoom:false,zoomControl:false});
    L.control.zoom({position:'topright'}).addTo(map);
    L.control.scale({imperial:false,position:'bottomleft'}).addTo(map);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,
      attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).on('tileerror',()=>{
        if(tileFailed)return;tileFailed=true;$('#map-status').classList.add('tile-warning');$('#map-status').textContent='Some map tiles could not load. Station markers and the list still show the published locations.';
      }).addTo(map);
    overlay=L.layerGroup().addTo(map);lines=L.layerGroup().addTo(map);
    $('#map-fit').addEventListener('click',()=>{overview=false;draw(true);});
    $('#map-overview').addEventListener('click',()=>{overview=!overview;draw(true);});
    $('#map-lines').addEventListener('click',()=>{showLines=!showLines;$('#map-lines').setAttribute('aria-pressed',String(showLines));if(showLines)lines.addTo(map);else map.removeLayer(lines);});
    $('#map-station-list').addEventListener('click',event=>{const button=event.target.closest('[data-map-station]');if(button)focusStation(button.dataset.mapStation);});
    if(globalThis.ResizeObserver)new ResizeObserver(()=>map.invalidateSize()).observe($('#station-map'));
    return true;
  }
  function stationDetails(station,index){
    selectedKey=key(station);
    const row=[...station.rows].reverse().find(r=>typeof r.temperature==='number')||station.rows.at(-1);
    const source=station.official?'OFFICIAL WEATHER STATION':'COMMUNITY MONITOR';
    $('#map-station-detail').innerHTML=`<p class="eyebrow">${index+1} / ${source}</p><h3>${esc(station.name)}</h3><div class="map-detail-values"><span class="map-detail-temp">${num(row?.temperature)}<small> °C</small></span><span class="map-detail-distance">${num(station.distance/1000)} km from the selected place</span></div><p class="map-detail-meta">${esc(station.provider)}${station.provider==='Météo-France'?' · published daily':''}<br>${row?esc(date(row.time))+' · Europe/Berlin':'No reading available'}<br>Humidity ${num(row?.humidity)}% · wind ${num(row?.wind)} km/h</p><a href="${esc(station.url?.startsWith('https://')?station.url:'https://www.openstreetmap.org/')}" target="_blank" rel="noopener">Station data & source ↗</a>`;
    for(const button of $('#map-station-list').querySelectorAll('[data-map-station]'))button.setAttribute('aria-pressed',String(button.dataset.mapStation===selectedKey));
    for(const [id,marker] of markers){const element=marker.getElement();if(element)element.classList.toggle('active',id===locationId+'|'+selectedKey);}
  }
  function selectFromMap(place,station,index){
    if(place.id!==locationId){overview=false;options.onLocationSelect?.(place.id);}
    stationDetails(station,index);
  }
  function popup(station){
    const row=station.rows.at(-1);
    return `<h3>${esc(station.name)}</h3>${esc(station.provider)}<br><strong>${num(row?.temperature)} °C</strong> · ${num(station.distance/1000)} km straight line<br>${row?esc(date(row.time)):''}${station.coordinates_approximate?'<br>Published coordinates are approximate.':''}`;
  }
  function draw(fit){
    if(!map||!data)return;
    overlay.clearLayers();lines.clearLayers();markers.clear();
    const selected=data.locations.find(l=>l.id===locationId),places=overview?data.locations:[selected],bounds=[];
    for(const place of places){
      const center=[place.latitude,place.longitude];bounds.push(center);
      L.marker(center,{icon:L.divIcon({className:'atlas-place-icon',html:'+',iconSize:[25,25],iconAnchor:[12,12]}),title:place.name,alt:place.name+' configured location',zIndexOffset:500})
        .bindTooltip(esc(place.name),{direction:'top',offset:[0,-13]}).on('click',()=>{if(place.id!==locationId){overview=false;options.onLocationSelect?.(place.id);}else{overview=false;draw(true);}}).addTo(overlay);
      const stations=options.getStations(place);
      stations.forEach((station,index)=>{
        if(!coordinates(station))return;
        const point=[station.latitude,station.longitude];bounds.push(point);
        L.polyline([center,point],{color:'#6d8b60',weight:1.5,opacity:.55,dashArray:'4 6',interactive:false}).addTo(lines);
        const marker=L.marker(point,{icon:L.divIcon({className:'atlas-station-icon',html:`<span class="station-rank ${station.official?'official':''}">${index+1}</span>`,iconSize:[28,28],iconAnchor:[14,14]}),
          title:`${index+1}. ${station.name} · ${num(station.distance/1000)} km`,alt:`${index+1}. ${station.name}, ${station.provider}, ${num(station.distance/1000)} km from ${place.name}`})
          .bindTooltip(`${esc(station.name)} · ${num(station.distance/1000)} km`,{direction:'top',offset:[0,-13]})
          .bindPopup(popup(station)).on('click',()=>selectFromMap(place,station,index)).addTo(overlay);
        markers.set(place.id+'|'+key(station),marker);
      });
    }
    $('#map-overview').setAttribute('aria-pressed',String(overview));
    $('#network-title').textContent=overview?'Three places, one monitoring network':selected.name+' · station network';
    if(!tileFailed)$('#map-status').textContent=overview?`${data.locations.length} places · ${data.locations.reduce((n,l)=>n+options.getStations(l).length,0)} monitors · select a place to focus`:`${current.length} monitors · numbered by distance from ${selected.street}`;
    if(fit&&bounds.length)map.fitBounds(L.latLngBounds(bounds).pad(.14),{padding:[32,32],maxZoom:13,animate:false});
    const chosen=current.find(s=>key(s)===selectedKey)||current[0];
    if(chosen)stationDetails(chosen,current.indexOf(chosen));
  }
  function render(nextData,nextLocationId,nextOptions){
    data=nextData;options=nextOptions;
    const stations=options.getStations(data.locations.find(l=>l.id===nextLocationId));
    const changed=lastKey!==data.collected_at+'|'+nextLocationId+'|'+stations.map(key).join(',');
    if(!changed)return;
    lastKey=data.collected_at+'|'+nextLocationId+'|'+stations.map(key).join(',');
    if(locationId!==nextLocationId){overview=false;selectedKey=null;}
    locationId=nextLocationId;current=stations;
    $('#map-list-label').textContent=`${current.length} nearby monitors`;
    $('#map-station-list').innerHTML=current.map((s,i)=>`<button type="button" class="map-station-row" data-map-station="${esc(key(s))}" aria-pressed="false"><span class="station-rank ${s.official?'official':''}">${i+1}</span><span class="station-name">${esc(s.name)}<small>${esc(s.provider)}</small></span><span class="station-numbers">${num(s.distance/1000)} / ${num(s.rows.at(-1)?.temperature)}°</span></button>`).join('');
    if(current.length)stationDetails(current[0],0);
    else $('#map-station-detail').innerHTML='<p class="eyebrow">STATION NETWORK</p><h3>No recent monitors available</h3><p class="fineprint">The map still shows the configured place.</p>';
    if(ensure())draw(true);
  }
  function focusStation(stationKey){
    if(!map)return;
    if(overview){overview=false;draw(true);}
    const station=current.find(s=>key(s)===stationKey),marker=markers.get(locationId+'|'+stationKey);
    if(!station||!marker)return;
    stationDetails(station,current.indexOf(station));map.panTo(marker.getLatLng(),{animate:false});marker.openPopup();
  }
  return {render,focusStation};
})();
