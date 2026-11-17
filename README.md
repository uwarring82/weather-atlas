# Weather Atlas

A public weather record for **Haßlinghausen, Steinklippe**, **Freiburg, Hermann-Herder-Straße**, and **Xonrupt-Longemer, France**: recent official station observations, a seven-day forecast comparison and an archive of the forecasts actually retrieved.

**[Open the atlas](https://uwarring82.github.io/weather-atlas/)** · [Latest JSON](https://uwarring82.github.io/weather-atlas/data/latest.json) · [Related work and provider comparison](docs/related-work.md)

## What it collects

| Data | Origin | Delivery |
| --- | --- | --- |
| German station observations | Deutscher Wetterdienst | Bright Sky |
| Xonrupt-Longemer station observations | Météo-France | Official Vosges hourly climate file, published daily |
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

`.github/workflows/update.yml` is scheduled for minute 17 of every hour (UTC). It also runs on pushes to `main` and manually through **Actions → Collect weather and publish Pages → Run workflow**. It checks normalization, fetches data, commits updated JSON and compressed raw responses, and deploys `site/` through GitHub Pages Actions. GitHub schedules are best effort and can be delayed. GitHub may disable scheduled workflows after 60 days without repository activity; successful data commits normally keep this repository active. A complete upstream outage preserves the prior dataset and still permits deployment of website fixes. Each source failure is recorded as stale or unavailable rather than replacing old data with fabricated values. Structural validation blocks malformed data. A separate freshness check requires collection within three hours and valid station temperature observations within three hours for DWD or 36 hours for the daily Météo-France file. A final post-deployment failure step makes collector crashes and frozen datasets fail the Actions job while still allowing valid fallback data and website fixes to deploy. The browser uses measurement age for station status as well, so re-downloading an unchanged file cannot make an old measurement look current. An invalid WU_STATIONS value is recorded as a configuration error; an unexpected community exception is isolated to that location and reported after fresh official data has been saved.

For a fork: enable Actions, set **Settings → Pages → Source → GitHub Actions**, and update the repository URLs and identifying `User-Agent` in `scripts/collect.py`. The job checks out the latest main branch and rebases the data commit before pushing, retrying a rejected push up to three times. No external automation service is needed.

## Data and archive

- `locations.json`: coordinates rounded to four decimal places, resolved from OpenStreetMap on 17 November 2026. German points represent the named streets; Xonrupt-Longemer represents the village centre (relation 86306). Adjust them here if a specific point is needed.
- `site/data/latest.json`: normalized observations and forecasts, provider status, retrieval timestamp, request URL, station provenance and model grid metadata.
- `site/data/archive/*.json.gz`: raw API responses and unmodified selected-station CSV rows, with collection time and request URLs. New collections are separate timestamped snapshots. Thirty days remain in the current tree; older committed snapshots can be recovered from Git history.
- `site/data/archive-index.json`: available raw snapshots. For example, `gzip -dc site/data/archive/<timestamp>.json.gz` reads one collection.

All persisted times are explicit UTC; the website displays **Europe/Berlin**, including daylight saving time. Temperature is °C, precipitation mm, wind km/h and humidity %. MET Norway wind is converted from m/s. Its next-hour precipitation is shifted to the hour ending timestamp to align with the preceding-hour convention used by the other sources. Multi-hour MET precipitation is left null, rather than divided into invented hourly values. Zero remains zero and unavailable values remain null. Chart lines break at null values and missing hourly observations or precipitation; forecast temperature, humidity and wind connect each model's native samples.

`fetched_at` means retrieval time. MET Norway also supplies a provider update time. Open-Meteo's endpoint does not supply the underlying model issue time here, so it is left null. Raw snapshots make future verification possible; this initial version does not yet rank forecast accuracy. A valid evaluation must match forecasts retrieved before an observation, compare equal lead times, account for the distance between model grid and station, and exclude post-observation updates.

## Attribution and licenses

Application code: [MIT](LICENSE). Weather data retains its upstream licenses; the code license does not relicense it.

- **Météo-France**: [official hourly dataset](https://www.data.gouv.fr/datasets/donnees-climatologiques-de-base-horaires), [Licence Ouverte 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence/). The nearest station with recent temperature data within 50 km is selected from Vosges department 88. Its daily-published file is checked hourly with If-Modified-Since; HTTP 304 preserves the original retrieval time and updates only checked_at. New Year requests fall back to the previous year’s filename on HTTP 404. Current station: Gérardmer, 7.0 km from the village centre, 669 m elevation. Available temperature and precipitation are displayed; unmeasured wind/humidity remain blank. Wind, when supplied, is converted from m/s; doubtful quality-code 2 readings are excluded while raw quality flags are archived. The archive stores the selected original CSV rows, not the full departmental file.
- **DWD** observations delivered by [Bright Sky](https://brightsky.dev/): [DWD open data terms](https://www.dwd.de/EN/service/copyright/copyright_node.html). Bright Sky's API implementation is MIT licensed. Values are normalized and visualized here.
- **Open-Meteo**, with **DWD, ECMWF and NOAA**: [data attribution license](https://open-meteo.com/en/license), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Its [free API terms](https://open-meteo.com/en/terms) cover noncommercial use; this atlas has no advertising or paid features.
- **MET Norway**: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [terms](https://api.met.no/doc/TermsOfService). Retrieved centrally with an identifying User-Agent; normalized wind units and precipitation timestamps as described above.
- Street coordinates: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL 1.0. [Steinklippe way](https://www.openstreetmap.org/way/28942613), [Hermann-Herder-Straße way](https://www.openstreetmap.org/way/4538046), [Xonrupt-Longemer relation](https://www.openstreetmap.org/relation/86306).

## Community and Weather Underground data

The default community feed uses [openSenseMap](https://docs.opensensemap.org/). It selects up to three nearby outdoor sensors with temperature readings from the past two hours. Air temperature must be between −35 and 55 °C; humidity must be between 0 and 100%. These are basic range checks, not a calibration guarantee. Names, distances, provider links and actual measurement times appear separately from official stations. Soil sensors are excluded. Community history grows from collection snapshots, with seven days retained even if a station temporarily stops reporting or drops out of the nearest three. Previously selected stations remain in the JSON as stale until their final reading ages out. The website shows cards only for the three nearest stations currently reporting. Observation charts show at most the three nearest community stations with data for the selected metric in the seven-day window; inactive stations are labeled recently seen. All retained readings remain in the download. Configured WU stations skipped for quality, distance, missing records or stale readings report a reason in the public errors list. openSenseMap data is published under [PDDL 1.0](https://opendatacommons.org/licenses/pddl/1-0/), as stated in its API documentation. `node tests/ui-smoke.cjs` exercises the rendering logic for all view combinations.

[Weather Underground's current PWS endpoint](https://www.wunderground.com/pws-api/observations/current-conditions) requires an authorized API key. The adapter is implemented but not enabled by default or verified against a live authorized WU account. To enable it:

1. Add a repository Actions **secret** named `WU_API_KEY` with your own API key.
2. Add an Actions **variable** named `WU_STATIONS` containing selected PWS IDs mapped to locations: `{"hasslinghausen":["YOUR_STATION_ID"],"freiburg":["YOUR_STATION_ID"],"xonrupt-longemer":["YOUR_STATION_ID"]}`.
3. Run the collection workflow. It accepts stations within 15 km, rejects expired or QC-rejected readings, and displays station identity and provider.

Use an API entitlement that permits your intended public display. The collector keeps the API key out of public files and error messages. It does not persist credential-bearing request URLs or WU raw responses. Daily cumulative rain is retained as `precipitation_today`, separate from hourly precipitation. Wind gusts accompany WU wind speeds. WU data retains its Weather Company license and is not bundled by default.

## Repository growth

Normalized JSON is pretty-printed so individual readings produce useful Git deltas. Compressed raw snapshots are still separate files and keep accumulating in Git history after the 30-day tree retention expires. The original two-location archive was about 27 KB per collection; France adds selected station rows. Budget for a few hundred MB per year rather than expecting deletion to shrink history. If that becomes inconvenient, move raw snapshots to a dedicated data repository or release assets and keep only an archive index in the application repository; existing history will need a separate migration.
