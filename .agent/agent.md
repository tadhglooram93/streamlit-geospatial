# Agent guide: streamlit-geospatial (fork)

This document summarizes the repository, how Earth Engine auth works in practice, and how agents should work here. The migration plan in §4 has been **executed**; the sections below reflect both the current state and the historical context for future maintainers.

> **Implementation status (current)**
>
> - Single-page Streamlit app: `Home.py` (the timelapse module) — multipage layout removed.
> - Earth Engine auth: service-account only, via `ee_auth.init_earth_engine()` reading `GCP_SERVICE_ACCOUNT_JSON` and `EE_PROJECT_ID` from the environment. `EARTHENGINE_TOKEN` is no longer used.
> - Hugging Face Space metadata lives in the YAML front matter of `README.md` (`sdk: docker`, `app_port: 7860`). Streamlit runs inside the repo `Dockerfile` (HF deprecated the standalone Streamlit SDK for new Spaces in 2025-04).
> - Optional credential smoke test: `scripts/smoke_test_ee.py` plus `.github/workflows/ee-smoke-test.yml` (weekly + manual dispatch).
> - **GitHub → Space sync**: `.github/workflows/sync_to_hub.yml` pushes `main` to the Hugging Face Space when `secrets.HF_TOKEN` and `vars.HF_SPACE_REPO` (`username/space-name`) are configured on the GitHub repository.

---

## 1. Repository summary

### Origin and purpose

- **Upstream**: [opengeos/streamlit-geospatial](https://github.com/opengeos/streamlit-geospatial) (community fork of Qiusheng Wu’s work; public demos have included [streamlit.gishub.org](https://streamlit.gishub.org) and a [Hugging Face Space by giswqs](https://huggingface.co/spaces/giswqs/Streamlit)).
- **This repo**: A **single-page Streamlit app** (`Home.py`) generating satellite timelapses for any region on Earth, using **Google Earth Engine** through **geemap** (Folium backend) and **streamlit-folium**. The upstream multipage demo has been collapsed to the timelapse experience only.

### Layout

| Path | Role |
|------|------|
| `Home.py` | The Streamlit app. Sets page config, sidebar "About", calls `init_earth_engine()`, renders the full timelapse UI (Landsat, Sentinel-2, GOES, MODIS, NAIP, custom EE collections). |
| `ee_auth.py` | Service-account-only Earth Engine init helper (`init_earth_engine`). Cached with `@st.cache_resource`. |
| `requirements.txt` | Python deps; uses `--find-links` for GDAL wheels; trimmed to `earthengine-api`, `geemap[extra]`, `streamlit`, `streamlit-folium`, `folium`, `geopandas`, `fiona`, `shapely`. |
| `Dockerfile` | Hugging Face **Docker** Space image: APT deps (same set as `packages.txt`), `pip install`, Streamlit on port **7860**. |
| `packages.txt` | Documented APT package list; kept in sync with the `Dockerfile` `apt-get install` line for transparency / local dev reference. |
| `README.md` | Hugging Face Space front matter (`sdk: docker`, `app_port: 7860`) + owner-friendly setup guide (GCP, EE, SA, HF, troubleshooting, handoff). |
| `.env.example` | Local development template for `GCP_SERVICE_ACCOUNT_JSON` and `EE_PROJECT_ID`. |
| `scripts/smoke_test_ee.py` | Minimal credential smoke test runnable locally or via GitHub Actions. |
| `.github/workflows/sync_to_hub.yml` | On push to `main`, force-pushes the repo to `https://huggingface.co/spaces/${HF_SPACE_REPO}` using `secrets.HF_TOKEN` and `vars.HF_SPACE_REPO`. |
| `.pre-commit-config.yaml` | Black (Jupyter), basic hygiene hooks, `nbstripout`. |

### Earth Engine usage (current)

- `Home.py` calls `init_earth_engine()` (from `ee_auth.py`) once when the app starts. The helper builds `ee.ServiceAccountCredentials` from `GCP_SERVICE_ACCOUNT_JSON` and calls `ee.Initialize(credentials, project=EE_PROJECT_ID)`. No interactive auth, no `EARTHENGINE_TOKEN`, no biweekly browser refresh.

### Timelapse functionality

The single-page app provides:

1. **Folium map** (`geemap.Map`) with draw tools and GeoJSON export; hybrid + roadmap basemaps.
2. **Geocode search** (`geemap.geocode`) to jump to a location.
3. **ROI**: upload GeoJSON/KML (via `geopandas`/`fiona`) or pick preset polygons (Landsat/GOES/MODIS/ocean samples).
4. **Collections** (selectbox): Landsat, Sentinel-2, GOES (incl. fire variant), MODIS NDVI/LST/ocean color, NAIP, arbitrary `ee.ImageCollection`.
5. **Exports**: GIF and optional MP4 (`geemap.*_timelapse` helpers); heavy server-side EE work plus local ffmpeg/gifsicle.

All collections were preserved during the migration; future maintainers can drop unused ones if cold-start time becomes an issue.

---

## 2. How authentication works today (critical for agents)

### Current path: `ee_auth.init_earth_engine`

`Home.py` calls `init_earth_engine()` from `[ee_auth.py](../ee_auth.py)`. The helper:

1. Reads `GCP_SERVICE_ACCOUNT_JSON` (full JSON of a Google Cloud service account key) from the environment. Raises a clear error if missing.
2. Parses the JSON and resolves the project id from `EE_PROJECT_ID` (preferred) or the JSON's `project_id` field.
3. Writes the JSON to a `0600`-permissioned temp file (because `ee.ServiceAccountCredentials` expects a file path), constructs credentials, calls `ee.Initialize(credentials, project=...)`, and removes the temp file.
4. Is wrapped in `@st.cache_resource(show_spinner=False)`, so each Streamlit rerun reuses the initialized Earth Engine session.

### Historical path: `EARTHENGINE_TOKEN` (deprecated in this fork)

The upstream demo used `geemap.coreutils.ee_initialize`, which reads `EARTHENGINE_TOKEN` as an OAuth refresh JSON (`client_id`, `client_secret`, `refresh_token`, `project`). That path is what required biweekly re-authentication when Google revoked the refresh token. It is no longer wired in this repo, but the variable name is still documented in the upstream README for context.

### Implications for agents

- **Do not** commit tokens, refresh payloads, or service-account JSON to git.
- Document **secret names** and **formats** only; store real values in **HF Space secrets** or **GitHub Actions secrets**.
- If you ever bring back OAuth (e.g. for a contributor who lacks GCP access), keep it as a **separate code path** in `ee_auth.py`—do not undo the SA default.

---

## 3. Best practices for agents in this repo

1. **Scope**: User goal is **timelapse-first** and **low infra**; avoid refactors unrelated to EE auth, HF deploy, or timelapse UX.
2. **Match existing style**: Streamlit patterns (`st.columns`, `st.session_state`, `@st.cache_data` / `@st.cache_resource`), geemap idioms (`geemap.Map`, `geemap.landsat_timelapse`, etc.). When adding UI, mirror the sidebar / form patterns already in `Home.py`.
3. **Dependencies**: Changing `requirements.txt` affects cold start and wheel compatibility on Linux. Keep the list trimmed; do not re-introduce `keplergl`, `leafmap`, `localtileserver`, `plotly`, or `pyarrow` unless they are actually imported.
4. **System packages**: Anything that shells out to **ffmpeg** / **gifsicle** / GDAL must keep `packages.txt` in sync.
5. **Secrets**: Never print or log `GCP_SERVICE_ACCOUNT_JSON`, key file paths, or HF tokens. Use **HF Space variables and secrets** (Settings → Variables and secrets); use **GitHub Actions secrets** for CI.
6. **Pre-commit**: Run `pre-commit run --all-files` before large Python edits if the contributor uses pre-commit locally.
7. **Testing**: No formal test suite. Quick checks: `python -c "import ee_auth"`, `python scripts/smoke_test_ee.py` (with secrets), `docker compose up --build` from the repo root (`.env` with EE secrets; same image as HF) and run one small Landsat timelapse, or `streamlit run Home.py` if using a native venv.

---

## 4. Migration plan (now implemented) and reference for future handoff

This section was originally a forward-looking plan; it has been executed. The historical structure is preserved because the GCP / IAM / handoff details are the same the next owner will need.

### 4.1 Goals recap

| # | Goal |
|---|------|
| G1 | **Private Hugging Face Space** running a **lightweight** app focused on **Timelapse** (Landsat / GOES / optional Sentinel-2). |
| G2 | **Reduce or eliminate** biweekly **manual** Google re-auth where possible. |
| G3 | **Single repo** that holds app code, deployment metadata, and **documentation** for secrets so the final owner can swap credentials without archaeology. |

### 4.2 Services, accounts, and tokens (checklist for ultimate owner)

Document these for “plug in when you take over”:

| Item | Purpose | Where to store (low infra) |
|------|---------|----------------------------|
| **Google Cloud project** | Billing + APIs; Earth Engine is tied to GCP. **Required.** | Owner’s GCP console |
| **Earth Engine access** | The Cloud project must be **registered** for Earth Engine (noncommercial / research tier where applicable). | Same project |
| **Service account JSON key** | The full JSON of a GCP service account key in an EE-enabled project; consumed by `ee_auth.init_earth_engine()`. **This is the auth path used by the deployed app.** | HF Space secret `GCP_SERVICE_ACCOUNT_JSON` (paste the entire JSON); GitHub Actions secret with the same name for the smoke-test workflow |
| **`EE_PROJECT_ID`** | GCP **project id** for `ee.Initialize(project=...)`. Optional — if omitted, derived from `project_id` inside the SA JSON. | HF Space variable / GitHub Actions secret |
| **Service account email** | Identifier like `name@PROJECT_ID.iam.gserviceaccount.com`. | Read from `client_email` in the SA JSON (no separate secret needed) |
| **Hugging Face account** | Owns the Space; can stay private. | N/A |
| **HF token with write** (optional) | Pushes GitHub `main` to the Space via `.github/workflows/sync_to_hub.yml` (not used by the Streamlit runtime). | GitHub Actions **secret** `HF_TOKEN`; repository **variable** `HF_SPACE_REPO` = `username/space-name` |
| **No separate “Earth Engine API key”** | EE uses service accounts, OAuth refresh bundles, or ADC—not a single REST-style API key. | — |

Keep **`.env.example`** (committed) listing variable **names** only; real values live in HF / GHA.

#### GCP is mandatory (clarification)

- **Service accounts only exist inside a GCP project.** You cannot create or download an EE-ready SA without Cloud Console / IAM.
- **OAuth (`EARTHENGINE_TOKEN`) also implies GCP**: geemap builds OAuth credentials with `quota_project_id=stored["project"]`; Earth Engine usage is still attributed to that Cloud project after registration.
- **Cost for this fork’s goal**: noncommercial / academic Earth Engine registration is typically **$0** for EE usage itself; HF CPU Spaces can stay free. You may still be prompted to **attach a billing account** to enable APIs—set [budget alerts](https://cloud.google.com/billing/docs/how-to/budgets) at **$0** if you want early warning. Avoid enabling unrelated billable products (GCS exports, BigQuery, VMs) unless you need them.

#### New project + Earth Engine + service account (console checklist)

Follow these once per owner (repeat at handoff). Official references: [Earth Engine Cloud project setup](https://developers.google.com/earth-engine/earthengine_cloud_project_setup), [Register project / EE console](https://console.cloud.google.com/earth-engine), [Enable Earth Engine API](https://console.cloud.google.com/apis/library/earthengine.googleapis.com), [Service accounts guide](https://developers.google.com/earth-engine/guides/service_account).

1. **Sign in** at [Google Cloud Console](https://console.cloud.google.com/) with the Google account that will own research billing/access (your friend’s ultimately).
2. **Create a project**: top bar → project picker → **New Project** → note the **Project ID** (lowercase id string). This value is what you pass as `EE_PROJECT_ID` / `project=` to `ee.Initialize`.
3. **Register Earth Engine on that project**: open [Earth Engine in Cloud Console](https://console.cloud.google.com/earth-engine) while the project is selected; complete registration for **noncommercial / research** (or the tier that matches your use case). Until registration succeeds, EE calls from any credential type will fail.
4. **Enable the Earth Engine API** on the same project: [API Library → Earth Engine API](https://console.cloud.google.com/apis/library/earthengine.googleapis.com) → **Enable**.
5. **Create a dedicated service account** (recommended): **IAM & Admin → Service accounts → Create**. Give it a clear name (e.g. `hf-timelapse`). Copy the **email** (`...@...gserviceaccount.com`).
6. **Grant IAM roles on the project** to that service account (next subsection)—do not skip **Service Usage Consumer**.
7. **Create a JSON key**: Service account → **Keys → Add key → JSON**. Download once; treat like a password. Store only in HF Space secrets (or a secret manager), never in git.
8. **Smoke-test locally** (optional): from a machine with `earthengine-api` installed, use the snippet from [Authenticate with a private key](https://developers.google.com/earth-engine/guides/service_account#authenticate_with_a_private_key) (`ee.ServiceAccountCredentials` + `ee.Initialize`). Confirm no auth errors before wiring HF.

#### IAM roles for the Hugging Face Streamlit service account

Earth Engine’s docs distinguish **view/list** vs **interactive computations**. This app runs **`geemap` timelapse helpers**, which execute EE computations server-side; grant sufficient EE scope on the **GCP project** for the service account principal.

Per Google’s [access control](https://developers.google.com/earth-engine/guides/access_control) and [full API access](https://developers.google.com/earth-engine/guides/access_control#full_access_to_the_earth_engine_api) guidance:

| Grant on the EE-enabled GCP project | Role ID | Why |
|-------------------------------------|---------|-----|
| **Service Usage Consumer** | `roles/serviceusage.serviceUsageConsumer` | Grants **`serviceusage.services.use`**, which Google documents as required so `ee.Initialize(project=YOUR_PROJECT_ID)` can use that Cloud project when calling APIs. Missing this commonly surfaces as initialize failures. |
| **Earth Engine Resource Writer** | `roles/earthengine.writer` | Safe default for **interactive computations** (timelapses, thumbnails, reductions). **Earth Engine Resource Viewer** (`roles/earthengine.viewer`) is mainly view/list; if computations fail with permission errors, step up to Writer. |

Add principals via **IAM & Admin → IAM → Grant access**: paste the service account email, add both roles, save.

If your organization forbids Writer, consult Google’s permission tables for a custom role—but Writer matches typical interactive EE Python usage.

**REST-only nuance:** If you later call EE REST endpoints directly, the same docs note **Earth Engine Resource Viewer** plus Service Usage Consumer as a baseline; this Streamlit app uses the **Python client**, which needs computation permissions—hence Writer by default.

### 4.3 Auth mode (now: service account only)

The implemented path is **service account + private key JSON** as documented in Google’s [Authenticate with a private key](https://developers.google.com/earth-engine/guides/service_account#authenticate_with_a_private_key) guide. `ee_auth.init_earth_engine()` builds `ee.ServiceAccountCredentials(client_email, key_file)` and calls `ee.Initialize(credentials, project=...)`. The biweekly browser refresh that the upstream OAuth path required is gone; rotate keys only on compromise or org policy.

OAuth via `EARTHENGINE_TOKEN` is intentionally **not** wired. If a future maintainer wants to bring it back as a fallback (e.g. for a contributor without GCP access), add it as a separate branch in `ee_auth.py` and document it in the README — do not undo the SA default.

### 4.4 Hugging Face Space (private) — current configuration

- **SDK**: Docker (`sdk: docker`, `app_port: 7860` in `README.md` front matter). Hugging Face deprecated the built-in Streamlit SDK when creating **new** Spaces ([changelog](https://huggingface.co/docs/hub/spaces-changelog), 2025-04-30); Streamlit apps now use a Docker image.
- **Container**: Root [`Dockerfile`](../Dockerfile) installs APT deps (mirroring `packages.txt`), `pip install -r requirements.txt`, and runs `streamlit run Home.py` bound to `0.0.0.0:7860`.
- **Python entry**: Still `Home.py` (single-page timelapse app).
- **Secrets** (Settings → Variables and secrets):
  - `GCP_SERVICE_ACCOUNT_JSON` — full SA JSON.
  - `EE_PROJECT_ID` — GCP project id (optional if the JSON has `project_id`).
- **Cold start**: still dominated by `geemap[extra]` and GDAL wheels. If the Space ever times out, consider dropping `[extra]` first.
- **Branch strategy**: `main` is what the Space tracks. Use a separate Space for staging credential changes if needed.

### 4.5 Codebase streamlining (executed)

What changed from upstream:

1. `pages/` removed entirely — the timelapse module became `Home.py`.
2. Unused assets removed: `data/`, `index.html`, `Procfile`, `setup.sh`.
3. Sidebar branding rewritten; upstream personal links removed.
4. `requirements.txt` trimmed to the minimum needed by `Home.py` (no `keplergl`, `leafmap`, `localtileserver`, `plotly`, `pyarrow`).
5. Auth helper extracted into `ee_auth.py`; `Home.py` calls `init_earth_engine()`.
6. Silent `try/except: pass` wrapper around `app()` replaced with one that surfaces errors to the user and re-raises.
7. Root `Dockerfile` + `sdk: docker` / `app_port: 7860` in `README.md` for Hugging Face (standalone Streamlit SDK removed from new-Space UI in 2025-04).

Future agents who want to slim further can drop unused collection branches in `Home.py` (e.g. NAIP, MODIS Ocean, Any EE ImageCollection) and remove `geemap.colormaps` if those branches go.

### 4.6 GitHub Actions

- **Earth Engine smoke test** (`.github/workflows/ee-smoke-test.yml`): weekly + manual; needs `secrets.GCP_SERVICE_ACCOUNT_JSON` and `secrets.EE_PROJECT_ID`.
- **Sync to Hugging Face Space** (`.github/workflows/sync_to_hub.yml`): on every push to `main` (and manual dispatch); needs `secrets.HF_TOKEN` and repository variable `vars.HF_SPACE_REPO` (`username/space-name`). This replaces a non-existent “link GitHub repo” button for Docker Spaces.

With service-account auth the EE smoke test is near-zero maintenance; the sync workflow is the standard way to keep the Hub Space identical to GitHub `main`.

### 4.7 Handoff to final owner (friend)

1. **GitHub**: Transfer repo ownership; add her as admin / transfer the HF Space to her account.
2. **GCP**: She repeats **§4.2** (new Cloud project → EE registration → enable EE API → create SA → IAM: Service Usage Consumer + Earth Engine Resource Writer → download JSON key).
3. **HF Space**: She replaces `GCP_SERVICE_ACCOUNT_JSON` and `EE_PROJECT_ID` with her own values, restarts the Space, and confirms a small timelapse renders.
4. **GitHub Actions**: She updates `HF_TOKEN`, `HF_SPACE_REPO`, `GCP_SERVICE_ACCOUNT_JSON`, and `EE_PROJECT_ID` at the repo level as needed.
5. **Revoke previous keys**: Delete the old SA JSON key from IAM → Keys after the new owner’s environment is green.
6. **Docs**: Point her to `README.md` for setup and to **§4.2** of this file for the IAM / GCP context.

### 4.8 Risk register (brief)

| Risk | Mitigation |
|------|------------|
| EE quota / request size | Smaller ROI, shorter date ranges; document limits in UI. |
| Large Docker / RAM on HF | Slim deps; consider `geemap` without `[extra]` if acceptable. |
| GDAL / fiona Linux wheels | Keep `--find-links` pattern or pin versions known to work on HF. |
| Private Space + collaborators | HF org or invite collaborators on the Space. |

---

## 5. Quick reference commands

```bash
# Local run (Docker — same image as Hugging Face)
docker compose up --build
```

```bash
# Local run (native venv; install APT deps from packages.txt yourself)
streamlit run Home.py
```

```bash
# Pre-commit (if installed)
pre-commit run --all-files
```

---

## 6. Related files to read before editing

- `Home.py` — the Streamlit app (timelapse UI, ROI handling, `init_earth_engine` call site).
- `ee_auth.py` — the Earth Engine credential helper.
- `requirements.txt`, `packages.txt` — Python and system deps.
- `README.md` — HF Space front matter + setup guide for the final owner.
- `scripts/smoke_test_ee.py`, `.github/workflows/ee-smoke-test.yml` — credential monitoring.

---

*Last updated: HF Spaces use Docker SDK (`sdk: docker`, port 7860) per 2025-04 changelog; repo includes root `Dockerfile`. Otherwise: single-page `Home.py`, `ee_auth.py` (`GCP_SERVICE_ACCOUNT_JSON` + `EE_PROJECT_ID`), optional weekly EE smoke test. `EARTHENGINE_TOKEN` OAuth path not wired.*
