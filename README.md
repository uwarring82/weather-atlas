# Weather Atlas

A public weather record for **Haßlinghausen, Steinklippe** and **Freiburg, Hermann-Herder-Straße**: seven days of nearby DWD observations, a seven-day forecast comparison, and an archive of the forecasts actually retrieved.

**[Open the atlas](https://uwarring82.github.io/weather-atlas/)** · [Latest JSON](https://uwarring82.github.io/weather-atlas/data/latest.json) · [Related work and provider comparison](docs/related-work.md)

## What it collects

| Data | Origin | Delivery |
| --- | --- | --- |
| Recent station observations | Deutscher Wetterdienst | Bright Sky |
| Outdoor citizen and hobby sensors | openSenseMap contributors | Up to three active outdoor stations within 15 km |
| Optional personal weather stations | Weather Underground contributors | WU PWS API, requires key and station configuration |
| ICON forecast | DWD | Open-Meteo `dwd_icon` |
| IFS forecast | ECMWF | Open-Meteo `ecmwf_ifs025` |
| GFS forecast | NOAA | Open-Meteo `gfs_seamless` |
| Locationforecast | MET Norway, using ECMWF outside its Nordic region | Direct MET Norway API |

Four forecast products do not mean four independent models: MET Norway's global product also uses ECMWF. The website describes model spread without presenting it as calibrated uncertainty. Each forecast's actual available horizon and temporal resolution may be shorter or coarser than the requested seven days.

Observations are measurements at nearby stations, not street-level sensors. Bright Sky may change its selected source between hours. Per-row source IDs, all station metadata and distances are retained. Forecast records from Bright Sky are explicitly excluded from observations. No reanalysis or past forecast is passed off as an observation.

## Run locally

Python 3.11+ and Node.js 22+ are enough; there are no package dependencies or API keys.

```sh
python3 scripts/collect.py
python3 -m unittest discover -s tests -v
python3 scripts/validate.py
node --check site/app.js
python3 -m http.server 8000 --directory site
```

Then open `http://localhost:8000`. The browser reads only the published JSON; it does not call weather APIs. Fonts load from Google Fonts with system fallbacks.

## Automatic collection and publishing

`.github/workflows/update.yml` runs at minute 17 of every hour (UTC), on pushes to `main`, and manually through **Actions → Collect weather and publish Pages → Run workflow**. It checks normalization, fetches data, commits updated JSON and compressed raw responses, and deploys `site/` through GitHub Pages Actions. GitHub schedules are best effort and can be delayed. GitHub may disable scheduled workflows after 60 days without repository activity; successful data commits normally keep this repository active. A complete upstream outage preserves the prior dataset and still permits deployment of website fixes. Each source failure is recorded as stale or unavailable rather than replacing old data with fabricated values.

For a fork: enable Actions, set **Settings → Pages → Source → GitHub Actions**, and update the repository URLs and identifying `User-Agent` in `scripts/collect.py`. No external automation service is needed.

## Data and archive

- `locations.json`: street coordinates, rounded to four decimal places, resolved from OpenStreetMap ways on 17 November 2026. These represent streets rather than buildings. Adjust them here if a specific point is needed.
- `site/data/latest.json`: normalized observations and forecasts, provider status, retrieval timestamp, request URL, station provenance and model grid metadata.
- `site/data/archive/*.json.gz`: raw responses with collection time and request URLs. New collections are separate timestamped snapshots. Thirty days remain in the current tree; older committed snapshots can be recovered from Git history.
- `site/data/archive-index.json`: available raw snapshots. For example, `gzip -dc site/data/archive/<timestamp>.json.gz` reads one collection.

All persisted times are explicit UTC; the website displays **Europe/Berlin**, including daylight saving time. Temperature is °C, precipitation mm, wind km/h and humidity %. MET Norway wind is converted from m/s. Its next-hour precipitation is shifted to the hour ending timestamp to align with the preceding-hour convention used by the other sources. Multi-hour MET precipitation is left null, rather than divided into invented hourly values. Zero remains zero and unavailable values remain null. Chart lines break at missing hourly samples, including MET's coarser long-range samples.

`fetched_at` means retrieval time. MET Norway also supplies a provider update time. Open-Meteo's endpoint does not supply the underlying model issue time here, so it is left null. Raw snapshots make future verification possible; this initial version does not yet rank forecast accuracy. A valid evaluation must match forecasts retrieved before an observation, compare equal lead times, account for the distance between model grid and station, and exclude post-observation updates.

## Attribution and licenses

Application code: [MIT](LICENSE). Weather data retains its upstream licenses; the code license does not relicense it.

- **DWD** observations delivered by [Bright Sky](https://brightsky.dev/): [DWD open data terms](https://www.dwd.de/EN/service/copyright/copyright_node.html). Bright Sky's API implementation is MIT licensed. Values are normalized and visualized here.
- **Open-Meteo**, with **DWD, ECMWF and NOAA**: [data attribution license](https://open-meteo.com/en/license), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Its [free API terms](https://open-meteo.com/en/terms) cover noncommercial use; this atlas has no advertising or paid features.
- **MET Norway**: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [terms](https://api.met.no/doc/TermsOfService). Retrieved centrally with an identifying User-Agent; normalized wind units and precipitation timestamps as described above.
- Street coordinates: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL 1.0. [Steinklippe way](https://www.openstreetmap.org/way/28942613), [Hermann-Herder-Straße way](https://www.openstreetmap.org/way/4538046).

## Community and Weather Underground data

The default community feed uses [openSenseMap](https://docs.opensensemap.org/). It selects up to three nearby outdoor sensors with temperature readings from the past two hours. Air temperature must be between −35 and 55 °C; humidity must be between 0 and 100%. These are basic range checks, not a calibration guarantee. Names, distances, provider links and actual measurement times appear separately from official stations. Soil sensors are excluded. Community history grows from hourly collection snapshots, with seven days retained. openSenseMap data is published under [PDDL 1.0](https://opendatacommons.org/licenses/pddl/1-0/), as stated in its API documentation. `node tests/ui-smoke.cjs` exercises the rendering logic for all view combinations.

[Weather Underground's current PWS endpoint](https://www.wunderground.com/pws-api/observations/current-conditions) requires an authorized API key. The adapter is implemented but not enabled by default or verified against a live authorized WU account. To enable it:

1. Add a repository Actions **secret** named `WU_API_KEY` with your own API key.
2. Add an Actions **variable** named `WU_STATIONS` containing selected PWS IDs mapped to locations: `{"hasslinghausen":["YOUR_STATION_ID"],"freiburg":["YOUR_STATION_ID"]}`.
3. Run the collection workflow. It accepts stations within 15 km, rejects expired or QC-rejected readings, and displays station identity and provider.

Use an API entitlement that permits your intended public display. The collector keeps the API key out of public files and error messages. It does not persist credential-bearing request URLs or WU raw responses. Daily cumulative rain is retained as `precipitation_today`, separate from hourly precipitation. Wind gusts accompany WU wind speeds. WU data retains its Weather Company license and is not bundled by default.
