# Job Pipeline

Containerised job-scraping pipeline targeting Dublin and EMEA Business Analyst, Data Analyst, CRM, and Systems roles. Built as a portfolio project demonstrating microservices architecture, container orchestration, workflow automation, and LLM-powered scoring.

## Overview

The pipeline scrapes job listings from Indeed and LinkedIn, persists structured CSVs to a shared Docker volume, and orchestrates the run through n8n. Future phases route results into Google Sheets and score each listing against a target CV using the Anthropic Claude API.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Docker Compose Stack                                    │
│                                                          │
│  ┌─────────────┐         ┌────────────────────────────┐  │
│  │ n8n         │  HTTP   │  jobspy-service            │  │
│  │ port 5678   │────────▶│  FastAPI + python-jobspy   │  │
│  │ orchestrate │         │  port 8000                 │  │
│  └─────────────┘         └──────────┬─────────────────┘  │
│                                     ▼                    │
│                ┌──────────────────────────────┐          │
│                │  shared_data (named volume)  │          │
│                │  timestamped jobs_*.csv      │          │
│                └──────────────────────────────┘          │
└──────────────────────────────────────────────────────────┘
```

## Stack

| Layer | Tool |
|---|---|
| Scraper service | Python 3.11, FastAPI, python-jobspy, pandas |
| Orchestration | n8n (self-hosted via Docker) |
| Containers | Docker Compose |
| Storage | Docker named volumes |
| LLM (Phase 4) | Anthropic Claude API |
| Sheets (Phase 2) | Google Sheets API via n8n |

## Endpoints

The jobspy service exposes a small REST API consumed by n8n.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/sources` | List supported boards (default vs all) |
| `GET` | `/role-families` | Return canonical role taxonomy |
| `GET` | `/files` | List CSVs already on disk |
| `POST` | `/scrape` | Run a single search; optionally persist CSV |

### Sample scrape request

```json
{
  "search_term": "Data Analyst",
  "location": "Dublin, Ireland",
  "sites": ["indeed", "linkedin"],
  "results_wanted": 30,
  "hours_old": 168,
  "role_family": "Data",
  "save_csv": true
}
```

## Run it locally

Prerequisites: Docker Desktop, ~2 GB free disk.

```bash
git clone https://github.com/<your-username>/job-pipeline.git
cd job-pipeline
docker compose up -d --build
```

Once both containers report `Up`:

- jobspy service: http://localhost:8000/health
- n8n editor:   http://localhost:5678 (set up an owner account on first launch)

A direct test of the scraper without n8n:

```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"search_term":"Data Analyst","location":"Dublin, Ireland","results_wanted":5}'
```

CSVs land in the `shared_data` volume. Copy them out with:

```bash
docker compose cp jobspy:/data/shared/. ./shared-data/
```

## Role taxonomy

Configurable via `app.py`. Default groupings:

| Family | Search terms |
|---|---|
| BA | Business Analyst, Senior Business Analyst, Business Systems Analyst |
| Data | Data Analyst, BI Analyst, Reporting Analyst |
| CRM_Salesforce | Salesforce Administrator, CRM Analyst, Sales Operations Analyst |
| Systems | Systems Analyst, Business Systems Integration |

## Architecture decisions

**Why a sidecar pattern, not a single combined image.** The official n8n image is hardened with no package manager, so scraping libraries cannot be installed inside it. A separate FastAPI container keeps n8n unmodified and lets the scraping service be versioned, scaled, and replaced independently.

**Why named volumes, not bind mounts.** Bind mounting host directories into Linux containers produced permission-related write failures (n8n runs as UID 1000, Windows mounts inherit different ownership). A named Docker volume sidesteps the issue entirely; outputs are accessed via `docker compose cp` when needed.

**Why jobspy owns CSV persistence, not n8n.** A bug in the n8n 2.x Read/Write Files node prevented writes to mounted volumes despite correct OS permissions. Moving persistence into the Python service was both a pragmatic fix and a cleaner separation of concerns: the scraper owns its outputs, n8n is purely an orchestrator.

**Why the role taxonomy lives in code, not config.** Search term groupings are intentionally part of the service contract. They appear in API responses (`GET /role-families`) and are used to tag rows during scrape, so consumers can group results downstream without re-deriving them.

## Phases

- [x] **Phase 1** — Containerised scraper, REST API, n8n orchestration, persistent CSV outputs
- [x] **Phase 2** — Google Sheets integration via n8n (OAuth2)
- [ ] **Phase 3** — Multi-search loops (all role families × multiple geos in one run)
- [ ] **Phase 4** — Claude-powered scoring against a target CV

## Project structure

```
job-pipeline/
├── docker-compose.yml
├── jobspy-service/
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── shared-data/          # gitignored — local outputs land here
├── .dockerignore
├── .gitignore
└── README.md
```