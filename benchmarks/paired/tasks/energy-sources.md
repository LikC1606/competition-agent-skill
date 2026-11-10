# UCI energy task: source evidence and protocol choices

Verified from the official UCI dataset page and dataset API on 2026-11-10.
This file contains evidence and benchmark design; it does not redistribute raw
data. `fetch_sources` keeps official HTML/API/ZIP bytes and hashes in the supplied
external cache.

## Direct official evidence

- [UCI dataset page](https://archive.ics.uci.edu/dataset/374/appliances+energy+prediction)
  identifies the dataset and states **CC BY 4.0**, linking the
  [license](https://creativecommons.org/licenses/by/4.0/legalcode).
- [UCI API](https://archive.ics.uci.edu/api/dataset?id=374) identifies 19,735
  instances, target `Appliances` in Wh, no missing values, dataset DOI
  `10.24432/C5VC8G`, and Luis Candanedo as creator.
- Its `additional_info.summary` describes 10-minute data over about 4.5 months,
  home temperature/humidity sensors averaged over 10-minute periods, and energy
  meters logged every 10 minutes. `variable_info` says the airport weather is
  hourly data subsequently interpolated, with permission to distribute that
  weather segment. The two `rv` variables are random model-testing inputs.
- [Official original ZIP](https://archive.ics.uci.edu/static/public/374/appliances+energy+prediction.zip)
  SHA-256: `2fccf354445d886e7917620b0195db1f3e3e34d5a067a93b844694a4c561255a`.
- Its `energydata_complete.csv` SHA-256:
  `2820bf712ad0275cb18b85a05250926100d8e65ebb9f4d2d016ca91ea152a25d`.
  Reading these pinned bytes confirms 19,735 rows in uninterrupted 10-minute
  order from 2016-01-11 17:00 to 2016-05-27 18:00. These dates and continuity
  checks are derived from the data, not claimed to be text quoted from UCI.

Attribution: Candanedo, Luis (2017). *Appliances Energy Prediction* [Dataset].
UCI Machine Learning Repository. DOI: 10.24432/C5VC8G. The introductory paper is
Candanedo, Feldheim and Deramaix, *Data driven prediction models of energy use of
appliances in a low-energy house*, Energy and Buildings 140 (2017), DOI
10.1016/j.enbuild.2017.01.083. The benchmark does not reproduce or claim the
paper's performance.

## Explicit benchmark design, not official dataset recommendations

Forecast the next logged interval using only previous completed rows. Exclude
same-row target/sensors/lights, interpolated airport weather, and random `rv`
columns. Retain past appliance/light values, prior home-sensor readings, causal
rolling means, and known calendar features. The public data stop before April
15; forward development windows start February 15, March 1, and March 15, with
a 24-hour training-label availability gap. May 1 onward is private confirmation.
Intermediate April 15–30 observations are used only to form causal history for
private features; they never become public training data.

Exact production sensor release delays and interval timestamp conventions are
not specified by UCI. The task explicitly assumes each previous interval is
available at prediction time and the target label arrives 600 seconds later.
Dataset timestamps remain naive chronology coordinates; no timezone is invented.
This is rolling one-step forecasting: past observed holdout values may enter
later private lag features, but models are never refitted on holdout targets.

Metric: pooled unweighted OOF RMSE in Wh. It is marked `proxy`, since this is a
local paired benchmark rather than an official competition scorer. The fixed
delivery rule averages the three already-trained fold models. Both workflow
versions receive byte-identical common infrastructure, including snapshotted
tabular training and metric code; this is not a separate ML-adapter ablation.

Private/cache folders must remain outside the agent filesystem view, and the
evaluator/protocol must be immutable. The original UCI data are public and can
be downloaded again, so an actual blind run also requires an enforced external
data-access policy. The task adapter validates inputs and artifacts; arbitrary
candidate Python and model deserialization are trusted code, not a sandbox.
