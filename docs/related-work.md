# Related work and source comparison

Weather Atlas combines a small, persistent local record with a provider comparison. It uses existing open weather infrastructure and keeps the observation/forecast distinction visible. Source documentation was checked on 17 November 2026.

| Project or service | What it contributes | Relationship to this atlas |
| --- | --- | --- |
| [Bright Sky](https://github.com/jdemaeyer/brightsky) and its [API documentation](https://brightsky.dev/docs/) | An accessible JSON API over DWD observations and MOSMIX forecasts | Used for recent station observations. Its `/weather` endpoint can include forecasts, so source types must be checked. |
| [Open-Meteo](https://open-meteo.com/en/docs) | Consistent interfaces across national weather models | Used to compare explicitly selected DWD ICON, ECMWF IFS and NOAA GFS products, rather than an unspecified best-match blend. |
| [MET Norway Locationforecast](https://docs.api.met.no/doc/locationforecast/datamodel.html) | A separately operated global point-forecast service | Used directly as a fourth forecast product. Outside the Nordic region it relies on ECMWF; it is not an independent fourth model. |
| [Meteostat](https://meteostat.net/) | Long-term station and place-based weather history | Useful for extending this atlas into seasonal and climate comparisons. It is not a live collection dependency. |
| [Wetterdienst](https://github.com/earthobservations/wetterdienst) | A Python toolkit for open weather data, including observations and forecasts | Useful if direct DWD ingestion, larger station catalogues or more weather services become necessary. The initial collector uses the Python standard library. |
| [DWD Climate Data Center](https://opendata.dwd.de/climate_environment/CDC/) and [MOSMIX](https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/) | Primary German observation archives and station-based forecast products | A direct-data route for reducing dependence on API intermediaries. Not counted as an independent source when it duplicates DWD content. |
| [Open-Meteo historical forecast API](https://open-meteo.com/en/docs/historical-forecast-api) | Archived operational model output | A potential backfill source. Retrieval snapshots are still necessary to know what this atlas actually had available at a given time. |

## Initial scope

The first version covers temperature, preceding-hour precipitation, wind speed and humidity. It stores seven recent days of station records and up to seven days of forecast data. The interactive chart and hourly table support both locations, each variable and two forecast horizons. Per-source status and retrieval age remain visible during partial outages.

## Useful next steps

Forecast verification should compare archived predictions at equal lead times against later observations at a consistently selected station. Report sample counts and station distance before adding rankings. Separate temperature error, precipitation amount error and event probabilities; these describe different questions. Do not treat agreement among models sharing an upstream source as independent evidence.

For local microclimates, a calibrated sensor at each street would provide stronger local evidence than a nearby official station. Its measurements should remain a distinct series with installation metadata. Longer-term climate summaries should use a stable station series and account for changes in location or instrumentation.

## Hobby and citizen weather stations

[openSenseMap](https://docs.opensensemap.org/) provides an open API for citizen sensors. This atlas selects nearby outdoor air-temperature sensors with recent readings, shows them as community observations and preserves their individual identities. Its data is available under PDDL 1.0. Basic freshness and plausible-range filtering cannot establish that a sensor is correctly shielded or calibrated.

[Weather Underground PWS](https://www.wunderground.com/pws-api) provides a broad personal weather station network and an authenticated API. A collector adapter is included, configured using an Actions secret and selected station IDs. It is disabled until credentials are supplied. The current-conditions product reports precipitation accumulated since midnight, which must not be compared as if it were an hourly rainfall total. Provider quality flags and observation age are retained.
