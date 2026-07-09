# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This repository is a HACS (Home Assistant Community Store) custom integration, `wadaco_water`, that pulls water consumption and invoice data from **Wadaco**'s customer-care portal (`cskh.wadaco.com.vn`) into Home Assistant as sensors. It intentionally mirrors the architecture of a sibling project, `eagent-dienlucvn` (an EVN electricity HACS integration by the same author), but trimmed down because Wadaco's backend is much simpler — see "Divergences from eagent_dienlucvn" below before assuming a pattern carries over unchanged.

## Repository layout

- `custom_components/wadaco_water/` — the HACS integration.
  - `const.py` — domain, API URLs, config keys, response-field IDs, default scan interval.
  - `wadaco_water.py` — the API client (`WadacoAPI`): `login()` for credential validation (returns the account's `org_code` from the response body — see below), `get_year_invoices()` / `request_update()` for data fetching, plus the `.NET` date parsing helper (`/Date(169...+0700)/` format) and the raw-JSON → sensor-data formatting (`_format_bill`, `_format_result`).
  - `config_flow.py` — single-step setup form (customer code + password + scan interval only — no branch code field, see below) and an options flow to change only the scan interval later.
  - `sensor.py` — `WadacoDevice` (owns the `DataUpdateCoordinator` for one customer account) and `WadacoSensor` (a generic `CoordinatorEntity` driven entirely by the `value_fn` on its `WadacoSensorEntityDescription`).
  - `types.py` — `WADACO_SENSORS`, the tuple of sensor descriptions; add a sensor by adding an entry here plus the matching `ID_*` key in `const.py` and field in `wadaco_water.py`'s formatting functions.
  - `strings.json` / `translations/{vi,en}.json` — config flow UI text (Vietnamese is primary; keep both in sync).
- `data_request/` — HAR captures used to reverse-engineer the API (gitignored, not part of the published component — see below).
- `hacs.json`, `README.md` (Vietnamese-language user docs), `LICENSE` (Apache 2.0).

## The Wadaco API (reverse-engineered from HAR captures)

Backend host: `myservice.citywork.vn` (a shared "gCare"/citywork.vn customer-care platform; the WordPress site at `cskh.wadaco.com.vn` is just the frontend for it).

- `POST /Mobile/LoginByUserCode` — body `{"userName": "<customerCode>", "password": "..."}` (just the customer code, **no branch prefix**). Response: `{"result": {..., "orgCode": "<branch code>", "access_token": "<JWT>", ...}, "message": ""}`. Used **only** to validate credentials during config flow — but the `orgCode` field in the response is the one piece of account metadata the user never types in themselves; `WadacoAPI.login()` pulls it out and the config flow saves it into the config entry (`CONF_ORG_CODE`) for every later `get_year_invoices()` call. Don't ask for org_code as a form field again — it isn't something the user can look up on their own.
- `GET /InVoices/findInVoicesByTime?maKhachHang=<customerCode>&limit=<n>&orgCode=<orgCode>&nam=<year>` — returns `{"result": [<invoice>, ...]}`, one entry per billing period for the given year. **No Authorization header or cookies are sent with this request in the captured traffic** — it needs no token at all.

Key invoice fields (Vietnamese key names, used as-is against the raw JSON in `wadaco_water.py`): `thang`/`nam` (period), `chiSoDau`/`chiSoCuoi` (old/new meter index), `tieuThu` (m³ consumed), `tongTien` (amount due), `daThanhToan` (bool, paid), `seriDongHo` (meter serial), `seriHoaDon`/`soHoaDon` (invoice series/number), `ngayDauKy`/`ngayCuoiKy`/`ngayDoc`/`ngayLapHoaDon` (period start/end/reading/invoice date, `.NET` `/Date(ms+tz)/` format), `dsChiTiet` (rate line items: `hangMucChiTiet`/`soLuong`/`donGia`/`thanhTien`), `mucVAT`/`phiVAT`, `mucBVMT`/`phiBVMT` (environment fee + rate), `phiThai` (wastewater fee), `tongTienBangChu` (amount in words). `_format_bill()` maps all of these into one flat dict — enough to fully render an invoice, not just show a total.

## Divergences from eagent_dienlucvn (read before copying patterns from it)

- **No session/token maintenance.** Since the invoice endpoint needs no auth, `WadacoDevice._async_update` just calls `api.request_update()` directly every cycle — there's no login-on-expiry retry loop like EVN's coordinator has. Don't reintroduce token refresh logic unless real traffic shows the API now requires it.
- **Higher default scan interval (12h, not 3h).** Water meters are hand-read once a month (~4th-6th), so polling more often than that is pointless. This is a deliberate product decision, not an oversight — don't "fix" it down to match the electricity integration.
- **Only the current year's invoice history is fetched** (`nam=<current year>`), not all-time history — matches what was asked for; extending to prior years would need a new coordinator query per year.
- Fewer sensors than the EVN integration (no daily consumption/cost, no Vietnamese tiered-pricing cost estimate) — water is billed by a flat rate per invoice line item (`dsChiTiet`), and cost estimation wasn't requested.
- **`org_code` is not a config-flow input.** Unlike EVN's merchant code (which the user types in), Wadaco's branch code comes back in the login response and is stored from there — see the API section above. The setup form only has customer code + password + scan interval.
- **History attribute is attached to three sensors, not just one.** `water_consumption`, `meter_index`, and `bill_amount` all set `history_key=ID_BILL_HISTORY` in `types.py`, so each exposes the full current-year invoice list (via `WadacoSensor.extra_state_attributes` in `sensor.py`) as its `history` attribute — every entry already carries enough fields (`_format_bill()`) to stand on its own, so there's no separate "consumption-only" history shape.

## Working conventions

- The HAR file in `data_request/` contains real account credentials, a real JWT, and a real customer name — it's already gitignored (`data_request/`, `sample/`), never remove that exclusion or copy those values into code, docs, or commits.
- No test suite, linter config, or build step exists in this repo. There's no `homeassistant` pip package installed in this environment either, so changes can only be checked with `python3 -m py_compile custom_components/wadaco_water/*.py` (syntax only) — validate actual logic (date parsing, field formatting) by loading `wadaco_water.py` standalone with stubbed `homeassistant.*` modules against the sample JSON in `data_request/`, the way it was done while building this integration.
