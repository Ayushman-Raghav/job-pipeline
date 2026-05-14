# Job Pipeline — Setup Guide

A step-by-step guide to running your own automated job search pipeline. By the end you will have a system that scrapes job boards for your target roles, writes every listing to your personal Google Sheet, and scores each one 0–10 against your candidate profile using a local AI model — all running on your laptop, no cloud costs, no API keys.

**Estimated time:** 60–90 minutes on a first install, including Google OAuth setup.

**What you need:**
- A laptop (Windows or Mac)
- A Google account (for Google Sheets)
- No programming experience required

> **Operating system:** Instructions cover both **Windows (PowerShell)** and **Mac (Terminal)**. Look for the `Windows` / `Mac` labels beside commands where they differ.

---

## Contents

1. [Checkpoint 0 — Hardware check](#checkpoint-0--hardware-check)
2. [Checkpoint 1 — Install prerequisites](#checkpoint-1--install-prerequisites)
3. [Checkpoint 2 — Clone the repo](#checkpoint-2--clone-the-repo)
4. [Checkpoint 3 — Environment file](#checkpoint-3--environment-file)
5. [Checkpoint 4 — Build your profile.json](#checkpoint-4--build-your-profilejson)
6. [Checkpoint 5 — Plan your search terms](#checkpoint-5--plan-your-search-terms)
7. [Checkpoint 6 — Create your Google Sheet](#checkpoint-6--create-your-google-sheet)
8. [Checkpoint 7 — Set up Google OAuth](#checkpoint-7--set-up-google-oauth)
9. [Checkpoint 8 — Start the Docker stack](#checkpoint-8--start-the-docker-stack)
10. [Checkpoint 9 — Pull the AI model](#checkpoint-9--pull-the-ai-model)
11. [Checkpoint 10 — Set up n8n](#checkpoint-10--set-up-n8n)
12. [Checkpoint 11 — Run the pipeline](#checkpoint-11--run-the-pipeline)
13. [Troubleshooting](#troubleshooting)
14. [Customising the pipeline](#customising-the-pipeline)
15. [Architecture reference](#architecture-reference)

---

## Checkpoint 0 — Hardware check

Before installing anything, confirm your machine meets these requirements:

| Requirement | Minimum | Notes |
|---|---|---|
| RAM | 8 GB | 16 GB recommended; the AI model needs headroom alongside Docker |
| Free disk space | 15 GB | Docker images (~3 GB) + AI model (~2 GB) + overhead |
| OS | Windows 10/11 (64-bit) or macOS 12+ | |
| Internet | Stable broadband | First-time download is ~3 GB total |

**Check your available RAM:**
- **Windows:** open Task Manager (`Ctrl+Shift+Esc`) → Performance → Memory
- **Mac:** open Activity Monitor → Memory tab

> If Docker Desktop is allocated less than 5 GB of memory, the 3B AI model will fail to load and return 500 errors on every scoring call. See [Checkpoint 9](#checkpoint-9--pull-the-ai-model) for how to handle this.

---

## Checkpoint 1 — Install prerequisites

### 1.1 — Docker Desktop

Docker runs the three services that make up the pipeline.

- **Windows:** https://www.docker.com/products/docker-desktop/ → Download for Windows
- **Mac:** https://www.docker.com/products/docker-desktop/ → choose Apple Silicon or Intel

Install it, then launch it. Wait for the whale icon (system tray on Windows, menu bar on Mac) to stop animating before continuing.

**Verify:**
```bash
docker --version
docker compose version
```
Both should print version numbers. If either errors, Docker is still starting — wait 30 seconds and retry.

---

### 1.2 — Git

**Windows:** download from https://git-scm.com/download/win and install with default settings.

**Mac:** usually pre-installed. Check:
```bash
git --version
```
If you see `command not found`:
```bash
xcode-select --install
```

---

### 1.3 — VS Code (recommended)

Not strictly required, but strongly recommended for editing `profile.json`. It highlights JSON errors in real time.

Download from: https://code.visualstudio.com/

---

## Checkpoint 2 — Clone the repo

Open **PowerShell** (Windows) or **Terminal** (Mac).

```bash
# Navigate to where you want the project folder

# Windows
cd $env:USERPROFILE

# Mac
cd ~

# Clone
git clone https://github.com/<repo-url>/job-pipeline.git
cd job-pipeline
```

**Verify:**
```bash
# Windows
dir

# Mac
ls
```

You should see: `jobspy-service/`, `workflows/`, `shared-data/`, `docker-compose.yml`, `README.md`, `.env.example`.

---

## Checkpoint 3 — Environment file

Copy the example environment file. The defaults work for a local setup — no secrets needed.

```bash
# Windows
Copy-Item .env.example .env

# Mac
cp .env.example .env
```

Open it to review:
```bash
code .env
```

Key settings (no changes needed for a standard install):

```
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_TIMEOUT=120
OLLAMA_CONCURRENCY=3
```

> If your Docker memory is below 5 GB, you may need to change `OLLAMA_MODEL`. See [Checkpoint 9](#checkpoint-9--pull-the-ai-model).

---

## Checkpoint 4 — Build your profile.json

This is the most important step. The AI reads this file when scoring each job. **The more accurate it is, the more meaningful your scores will be.**

### 4.1 — Start from the example

```bash
# Windows
Copy-Item jobspy-service\profile.example.json jobspy-service\profile.json

# Mac
cp jobspy-service/profile.example.json jobspy-service/profile.json
```

### 4.2 — Open it

```bash
code jobspy-service/profile.json
```

### 4.3 — Fill in every section

Replace every placeholder value with your real information. **Do not change the key names, brackets, or quote characters — only the values inside them.**

---

#### `candidate` — who you are

```json
"candidate": {
  "name": "Your Full Name",
  "current_location": "City, Country",
  "willing_to_relocate": ["City 1", "City 2", "Remote"],
  "right_to_work": "Your work authorisation status"
}
```

| Field | What to put |
|---|---|
| `name` | Your full name |
| `current_location` | Where you currently live — e.g. `"Dublin, Ireland"` |
| `willing_to_relocate` | List of locations you'd move to, or `["Remote"]` if fully remote |
| `right_to_work` | e.g. `"EU Citizen"`, `"UK Graduate Visa"`, `"Requires H-1B sponsorship"` |

---

#### `experience` — your background

```json
"experience": {
  "total_years": 5,
  "current_seniority": "Your Current Job Title",
  "current_employer": "Your Current Company",
  "previous_employer": "Your Previous Company",
  "domains": ["Industry 1", "Industry 2"]
}
```

| Field | What to put |
|---|---|
| `total_years` | Years of relevant experience — a number, no quotes |
| `current_seniority` | Your current job title |
| `current_employer` | Your current company |
| `previous_employer` | Most recent previous company |
| `domains` | Industries or business domains you have worked in |

---

#### `education`

```json
"education": {
  "highest": "BSc Computer Science",
  "university": "University Name",
  "year": 2021
}
```

---

#### `certifications`

```json
"certifications": [
  "Certification One",
  "Certification Two"
]
```

If you have none: `"certifications": []`

---

#### `core_skills` — group your skills by category

```json
"core_skills": {
  "category_one": ["Skill A", "Skill B", "Skill C"],
  "category_two": ["Skill D", "Skill E"]
}
```

Use any category names that fit your field. Examples by profession:

| Profession | Example categories |
|---|---|
| Software Engineer | `languages`, `frameworks`, `cloud`, `tools` |
| Data Analyst | `data_and_reporting`, `platforms`, `automation` |
| Project Manager | `project_management`, `agile`, `tools` |
| Marketing | `channels`, `tools`, `analytics` |
| Finance | `financial_analysis`, `tools`, `reporting` |

Be specific — `"SQL (window functions, CTEs)"` is more useful to the scorer than just `"SQL"`.

---

#### `target_roles` — what you want

```json
"target_roles": {
  "preferred": [
    "Your Primary Target Role",
    "Another Role You Want"
  ],
  "acceptable": [
    "A Role You Would Accept But Is Not First Choice"
  ],
  "avoid": [
    "Roles You Do Not Want",
    "e.g. Junior roles, unrelated functions"
  ]
}
```

> **Tip:** be honest with the `avoid` list. If you don't want junior roles, add `"Junior / Graduate roles"`. If you don't want pure coding roles, add `"Software Engineer"`. A well-populated avoid list makes your 0-scores meaningful.

---

#### `preferences` — salary and work style

```json
"preferences": {
  "salary_min_eur": 50000,
  "salary_target_eur": 70000,
  "company_size": "any",
  "industries_preferred": ["Industry A", "Industry B"],
  "industries_avoid": ["Industry C"],
  "remote_ok": true,
  "hybrid_ok": true,
  "fully_onsite_ok": false
}
```

| Field | What to put |
|---|---|
| `salary_min_eur` | Minimum salary you'd accept — a number, no commas |
| `salary_target_eur` | Your target salary |
| `company_size` | `"startup"`, `"mid-size"`, `"enterprise"`, or `"any"` |
| `industries_preferred` | Industries you actively want |
| `industries_avoid` | Industries you want to filter out |
| `remote_ok` / `hybrid_ok` / `fully_onsite_ok` | `true` or `false` |

> Salary fields are used only by the AI as scoring context. They are not sent to any external service.

---

#### `strengths_to_highlight`

```json
"strengths_to_highlight": [
  "Specific achievement or capability — the more concrete the better",
  "Another strength",
  "Another strength"
]
```

Write 4–7 short bullets. Specific beats vague: `"Built 20+ dashboards replacing manual Excel reporting"` is more useful than `"experienced with data visualisation"`.

---

#### `things_that_dont_fit`

```json
"things_that_dont_fit": [
  "Pure coding / software engineering roles",
  "Junior or graduate-level positions",
  "Roles requiring more experience than I have"
]
```

---

### 4.4 — Validate the JSON

```bash
# Windows
Get-Content jobspy-service\profile.json | ConvertFrom-Json | Out-Null
# No output = valid. A red error means a syntax problem — missing comma, bracket, or quote.

# Mac
python3 -m json.tool jobspy-service/profile.json > /dev/null && echo "Valid JSON ✓"
```

> **After any future profile update:** clear the score cache so existing jobs get re-scored against the new profile:
> ```bash
> curl -X DELETE http://localhost:8000/score-cache
> ```

---

## Checkpoint 5 — Plan your search terms

Before setting up n8n, decide what you want to search for. You'll enter these into the workflow in Checkpoint 10.

### Role families

A role family is a short label + a search term that goes to Indeed and LinkedIn. You need 1–5.

**Rule of thumb:** use the exact phrase a recruiter would type into a job board. `"Senior Business Analyst"` returns more relevant results than just `"analyst"`.

**Examples by profession:**

| Profession | Label | Search term |
|---|---|---|
| Project Manager | `PMO` | `"PMO Analyst"` |
| Project Manager | `PM` | `"IT Project Manager"` |
| Software Engineer | `Backend` | `"Backend Software Engineer"` |
| Software Engineer | `Fullstack` | `"Full Stack Developer"` |
| Data Analyst | `Data` | `"Data Analyst"` |
| Data Analyst | `BI` | `"BI Analyst"` |
| Marketing | `Content` | `"Content Marketing Manager"` |
| Finance | `FPA` | `"Financial Planning Analyst"` |
| HR | `HRBP` | `"HR Business Partner"` |
| UX | `Design` | `"UX Designer"` |

### Locations

Pick 1–3 locations. Each location × each role family = one search request.

> **Total searches = role families × locations.** 3 roles × 2 locations = 6 searches. Keep it under 10 to avoid rate limiting from job boards.

**Country codes for Indeed** (used in the workflow config):

| Location | `country_indeed` value |
|---|---|
| Ireland | `"ireland"` |
| United Kingdom | `"uk"` |
| United States | `"usa"` |
| Canada | `"canada"` |
| Australia | `"australia"` |
| Netherlands | `"netherlands"` |
| Germany | `"germany"` |
| France | `"france"` |
| India | `"india"` |

---

## Checkpoint 6 — Create your Google Sheet

### 6.1 — Create a new spreadsheet

1. Go to https://sheets.google.com
2. Click **Blank**
3. Rename it (click "Untitled spreadsheet") to something like `Job Pipeline Results`

### 6.2 — Add the column headers

Click cell **A1**, then paste the following directly into the **formula bar** (`fx` field at the top of the page — not into the cell itself):

```
scraped_at	role_family	site	title	company	location	date_posted	is_remote	job_url	min_amount	max_amount	currency	search_term	description	fit_score	fit_reason
```

> These values are **tab-separated**. Pasting into the formula bar distributes them across columns A–P automatically.

**Verify:**
- A1 = `scraped_at`
- D1 = `title`
- I1 = `job_url`
- O1 = `fit_score`
- P1 = `fit_reason`

### 6.3 — Check for hidden whitespace

Hidden spaces in headers are invisible but silently break n8n's column mapping.

Click an empty cell (e.g. Q1) and type `=LEN(D1)`. It should return `5` (the exact length of "title"). If it returns `6` or more, there is a stray space — retype that cell manually and re-check.

### 6.4 — Copy your Sheet ID

Look at the browser URL:
```
https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit#gid=0
```
Copy the long string between `/d/` and `/edit`. You will paste it into n8n in Checkpoint 10.

---

## Checkpoint 7 — Set up Google OAuth

n8n needs permission to read and write your Google Sheet. This requires a Google Cloud OAuth app. **Allow ~20 minutes and follow each sub-step exactly.**

### 7.1 — Open Google Cloud Console

Go to https://console.cloud.google.com/ — accept terms if prompted. The free tier covers everything needed here.

### 7.2 — Create a project

1. Click the project dropdown at the very top of the page
2. Click **New Project**
3. Name it `job-pipeline-n8n`
4. Click **Create**, then switch to the new project using the same dropdown

### 7.3 — Enable the Google Sheets API

1. Left sidebar → **APIs & Services** → **Library**
2. Search `Google Sheets API` → click it → click **Enable**
3. Wait ~10 seconds for it to activate

### 7.4 — Configure the OAuth consent screen

1. Left sidebar → **APIs & Services** → **OAuth consent screen**
2. Select **External** → click **Create**
3. Fill in:
   - **App name:** `Job Pipeline`
   - **User support email:** your Gmail address
   - **Developer contact email:** your Gmail address
4. Click **Save and Continue**
5. **Scopes screen:** click **Save and Continue** (no changes needed — n8n handles scope requests)
6. **Test users:** click **+ Add Users** → add your own Gmail address → **Save and Continue**
7. Click **Back to Dashboard**

### 7.5 — Create OAuth credentials

1. Left sidebar → **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. **Application type:** Web application
4. **Name:** `n8n local`
5. Under **Authorized redirect URIs** → **+ Add URI** → paste exactly:
   ```
   http://localhost:5678/rest/oauth2-credential/callback
   ```
6. Click **Create**
7. Copy both the **Client ID** and **Client Secret** from the popup and save them temporarily — you will need them in Checkpoint 10.

> The redirect URI must be `http` (not `https`) and must not have a trailing slash. An exact match is required.

---

## Checkpoint 8 — Start the Docker stack

From inside the `job-pipeline` folder:

```bash
docker compose up -d
```

On first run this downloads and builds all images (~3 GB total). Expected time: 5–15 minutes.

**Verify all containers are running:**
```bash
docker compose ps
```

Expected:
```
NAME              STATUS
jobspy-service    Up
n8n               Up
ollama            Up
n8n-init          Exited (0)    ← correct — this is a one-shot init container
```

**Verify the jobspy service is healthy:**
```bash
# Windows
(Invoke-WebRequest http://localhost:8000/health).Content

# Mac
curl http://localhost:8000/health
```

Expected response: `{"status":"ok","service":"jobspy-service","version":"3.0.0"}`

---

## Checkpoint 9 — Pull the AI model

The Ollama container is running but has no model yet.

### 9.1 — Check Docker's memory allocation

1. Open **Docker Desktop** → gear icon → **Resources** → **Advanced**
2. Note the **Memory** value

| Docker memory | Model to use |
|---|---|
| 5 GB or more | `llama3.2:3b` — better reasoning, recommended |
| Less than 5 GB | `llama3.2:1b` — lighter, still effective |

### 9.2 — Increase Docker memory if needed

If your Docker memory is below 5 GB but your laptop has 8 GB+ of physical RAM:
1. Docker Desktop → **Resources** → **Advanced**
2. Drag the Memory slider up to **6 GB**
3. Click **Apply & Restart** and wait for Docker to come back up

### 9.3 — Pull the model

**3B model (recommended):**
```bash
docker exec -it ollama ollama pull llama3.2:3b
```

**1B model (if memory is limited):**
```bash
docker exec -it ollama ollama pull llama3.2:1b
```

If you pulled the 1B model, update `.env`:
```
OLLAMA_MODEL=llama3.2:1b
```
Then restart to apply: `docker compose up -d`

Expected download time: 5–20 minutes. A progress bar shows the download.

**Verify the model loaded correctly:**
```bash
docker exec ollama ollama list
# Should show the model name and size

# Quick test:
# Windows
(Invoke-WebRequest -Method POST http://localhost:11434/api/generate `
  -ContentType "application/json" `
  -Body '{"model":"llama3.2:3b","prompt":"Reply with OK only.","stream":false}').Content

# Mac
curl -s -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2:3b","prompt":"Reply with OK only.","stream":false}'
```

The test should return a JSON response with `"response"` containing some text. A 500 error here means Docker memory is too low — go back to step 9.2.

---

## Checkpoint 10 — Set up n8n

### 10.1 — Open n8n

Go to http://localhost:5678

Create a local owner account (email + password — this account only exists on your local n8n instance, nothing is sent to the internet).

### 10.2 — Import the workflow

1. Click **Workflows** in the left sidebar
2. Click **+ Add workflow**
3. On the canvas, click the **⋯** menu (top right) → **Import from File**
4. Select `workflows/job-pipeline-phase-4.json` from your project folder
5. The 11-node workflow appears:

```
Manual Trigger → Build search configs → HTTP Request (scrape)
→ Aggregate → Code (flatten + dedupe) → Append or update row in sheet
→ Read unscored rows → Bundle for batch scoring → Score batch (Ollama)
→ Fan out scores → Write scores to sheet
```

### 10.3 — Set YOUR search terms in "Build search configs"

1. Double-click the **Build search configs** node
2. Replace the `ROLE_FAMILIES` object and `GEOS` array with your own values from Checkpoint 5:

```javascript
// ── EDIT THIS SECTION ──────────────────────────────────────────
// Add one entry per role you want to search for.
// The key is a short label; the value is the search term sent to Indeed/LinkedIn.
const ROLE_FAMILIES = {
  Label1: "Your Search Term One",
  Label2: "Your Search Term Two",
  Label3: "Your Search Term Three",
};

// Add one entry per location you want to search.
// country_indeed must be the lowercase country name (see table in Checkpoint 5).
const GEOS = [
  { location: "Your City, Your Country", country_indeed: "yourcountry" },
  { location: "Another City, Country",   country_indeed: "anothercountry" },
];
// ── END OF EDITABLE SECTION ────────────────────────────────────
```

**Leave everything below that unchanged.** The rest of the node handles results_wanted, hours_old, sites, and save_csv — the defaults work fine.

3. Click **Back** to close the node

**Examples:**

Software Engineer in the US:
```javascript
const ROLE_FAMILIES = {
  Backend:   "Backend Software Engineer",
  Fullstack: "Full Stack Developer",
  Platform:  "Platform Engineer",
};
const GEOS = [
  { location: "San Francisco, CA", country_indeed: "usa" },
  { location: "New York, NY",      country_indeed: "usa" },
];
```

Finance Analyst in Ireland:
```javascript
const ROLE_FAMILIES = {
  FPA:       "Financial Planning Analyst",
  Finance:   "Finance Analyst",
  Reporting: "Management Accountant",
};
const GEOS = [
  { location: "Dublin, Ireland", country_indeed: "ireland" },
];
```

### 10.4 — Connect your Google Sheets credential

1. Click any **Google Sheets** node (e.g. "Append or update row in sheet")
2. In the right panel → **Credential to connect with** → **+ Create New Credential**
3. Select **Google Sheets OAuth2 API**
4. Paste your **Client ID** and **Client Secret** from Checkpoint 7.5
5. Click **Sign in with Google**
6. Choose the Google account that owns your Sheet
7. You will see an "unverified app" warning → click **Advanced** → **Go to Job Pipeline (unsafe)**

   > This warning appears because the OAuth app hasn't gone through Google's publisher verification process (which is only required for apps distributed publicly). You created this app in your own Google Cloud project — it is safe.

8. Click **Allow** → the credential is saved in n8n

### 10.5 — Point all three Google Sheets nodes at your sheet

Do this for each of: **Append or update row in sheet**, **Read unscored rows**, **Write scores to sheet**.

For each node:
1. Click the node
2. **Document** field → click the dropdown → select your sheet by name
   - If it doesn't appear, click the refresh icon next to the dropdown
3. **Sheet** field → select `Sheet1`
4. Click **Back**

### 10.6 — Save the workflow

`Ctrl+S` (Windows) or `Cmd+S` (Mac).

---

## Checkpoint 11 — Run the pipeline

### 11.1 — Execute

Click **Execute Workflow** (the play button at the bottom centre of the canvas).

### 11.2 — What happens and how long it takes

| Phase | Typical duration | What to watch |
|---|---|---|
| Scrape | ~5 minutes | HTTP Request node loops once per search config |
| Flatten + deduplicate | Seconds | Code node removes URL duplicates across searches |
| Upsert to Sheets | ~1 minute | Your Google Sheet fills with job rows |
| Read unscored rows | Seconds | n8n reads back rows where `fit_score` is empty |
| Batch scoring | 20–50 minutes | AI scores every job against your profile |
| Write scores | ~1 minute | `fit_score` and `fit_reason` columns fill in |

Total first run: roughly **30–60 minutes** depending on how many jobs were found.

### 11.3 — Monitor scoring progress

```bash
docker logs jobspy-service --follow
```

You will see lines like:
```
score-batch: 120 input, 0 cached, 120 to score, concurrency=3
score-batch: 10/120 new scored
score-batch: 20/120 new scored
...
score-batch: done in 720.4s — 120 ok (0 from cache), 0 errors
```

Press `Ctrl+C` to stop watching the logs (the pipeline continues running).

### 11.4 — Read your results

Open your Google Sheet and **sort column O (`fit_score`) descending**. Your best-matched roles appear at the top, each with a one-sentence explanation.

**Score guide:**

| Score | Meaning |
|---|---|
| 9–10 | Excellent fit — role, level, location, and skills all align |
| 7–8 | Strong fit — minor gaps, worth applying |
| 4–6 | Partial fit — stretch role or one dimension off |
| 1–3 | Weak fit — mostly mismatched |
| 0 | Explicit avoid — role type or industry you listed as a non-fit |

---

## Troubleshooting

### "Cannot connect to Docker daemon"
Docker Desktop is not running. Open it from Start menu (Windows) or Applications (Mac) and wait for the whale icon to stop animating before retrying.

### "Connection refused" on http://localhost:8000
The jobspy-service container hasn't finished starting. Run `docker compose ps`. If it shows `Restarting`, check its logs: `docker logs jobspy-service --tail 50`.

### All jobs show "Scoring failed — see error"
The AI model failed to load inside Ollama. Check:
```bash
docker logs ollama --tail 30
```
If you see `"model request too large for system"`, Docker doesn't have enough memory. Go to Docker Desktop → Resources → Advanced → increase Memory to at least 5 GB → Apply & Restart. If your machine can't spare that much RAM, switch to the 1B model (see [Checkpoint 9](#checkpoint-9--pull-the-ai-model)).

### Google OAuth shows "redirect_uri_mismatch"
The redirect URI in Google Cloud doesn't exactly match. Go back to Checkpoint 7.5 and confirm it is:
```
http://localhost:5678/rest/oauth2-credential/callback
```
No trailing slash. `http` not `https`.

### Google Sheets node shows "403 Forbidden"
The OAuth credential needs to be reconnected. In n8n → Settings → Credentials → find your Google Sheets credential → click **Reconnect** → complete the Google sign-in flow again.

### Google Sheets node shows "schema not detected" or columns map incorrectly
Hidden whitespace in your sheet headers. Click each header cell, check `=LEN(A1)` etc., retype any cell where the length doesn't match the header name exactly. Then in the n8n node, click the column mapping dropdown → **Refresh**.

### `fit_score` column stays empty after the workflow finishes
Two possible causes:
1. **Read unscored rows filtered everything out.** Open that node and confirm the filter is set to `fit_score is empty`.
2. **Scoring completed but n8n disconnected during the long call.** Run `docker logs jobspy-service --tail 10`. If it says "score-batch: done", scoring finished successfully — re-run the workflow and cached scores return instantly.

### Scores seem wrong after updating profile.json
The old scores are cached. Clear the cache to force re-scoring:
```bash
# Windows
(Invoke-WebRequest -Method DELETE http://localhost:8000/score-cache).Content

# Mac
curl -X DELETE http://localhost:8000/score-cache
```
Then re-run the workflow.

### "Port already in use" on 8000, 5678, or 11434
Another application is using that port. Stop it, or edit `docker-compose.yml` to map a different host port (e.g. change `"8000:8000"` to `"8001:8000"`).

---

## Customising the pipeline

### Change your target roles or locations
Open the **Build search configs** node in n8n and edit `ROLE_FAMILIES` and `GEOS`. Each role family × each geo = one search. See Checkpoint 10.3 for the full format and examples.

### Search more results per role
In **Build search configs**, increase `results_wanted` (max 100):
```javascript
results_wanted: 25,   // default is 15
```

### Widen the recency window
Increase `hours_old` to look further back (max 720 = 30 days):
```javascript
hours_old: 336,   // 2 weeks; default is 168 (1 week)
```

### Update your profile
Edit `jobspy-service/profile.json` and save. Changes take effect immediately on the next scoring call — no Docker rebuild needed. Clear the score cache afterwards if you want already-scraped jobs re-evaluated.

### Switch to a more powerful model
Llama 3.1 8B gives sharper scoring at the cost of ~4x slower inference. Requires ~6 GB Docker memory.
```bash
docker exec -it ollama ollama pull llama3.1:8b
```
Update `.env`: `OLLAMA_MODEL=llama3.1:8b`, then restart: `docker compose up -d`

### Run daily
Open n8n and click **Execute Workflow** again at any time. Previously-scored jobs are returned from the disk cache in milliseconds — only new listings cost inference time.

---

## Day-to-day usage

Once set up, the routine is simple:

1. Open Docker Desktop (if not already running)
2. Go to http://localhost:5678
3. Click **Execute Workflow**
4. ~5 minutes for scraping and sheet update
5. New jobs score automatically; cached jobs return instantly
6. Sort your sheet by `fit_score` descending

**Stop the stack when not using it:**
```bash
docker compose stop
```

**Start it again:**
```bash
docker compose start
```

---

## Architecture reference

Three containers, one shared volume, one Docker bridge network:

```
┌─────────────────────────────────────────────────────┐
│  Docker bridge network: pipeline                    │
│                                                     │
│  ┌──────────────┐    ┌──────────────┐               │
│  │     n8n      │───▶│   jobspy-    │               │
│  │   :5678      │    │   service    │               │
│  │ (orchestrator│    │   :8000      │               │
│  │   + UI)      │    │ (scraper +   │               │
│  └──────────────┘    │  scorer)     │               │
│                      └──────┬───────┘               │
│                             │                       │
│                      ┌──────▼───────┐               │
│                      │   ollama     │               │
│                      │   :11434     │               │
│                      │  (local LLM) │               │
│                      └──────────────┘               │
│                                                     │
│  Shared volume: /data/shared                        │
│  ├── jobs_*.csv              (scraped job CSVs)     │
│  └── score_cache.json        (scored URL cache)     │
└─────────────────────────────────────────────────────┘
                      │
              Google Sheets API
              (your personal sheet,
               via your own OAuth2 app)
```

| Container | Port | Role |
|---|---|---|
| `jobspy-service` | 8000 | Scrapes job boards; scores jobs against your profile; manages the disk cache |
| `n8n` | 5678 | Orchestrates the pipeline; provides the visual workflow canvas; calls jobspy and Google Sheets |
| `ollama` | 11434 | Runs the AI model locally; receives scoring prompts from jobspy-service |

**Key endpoints on jobspy-service:**

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/scrape` | Scrape one search term × location combination |
| POST | `/score-batch` | Score many jobs with bounded concurrency + disk cache |
| GET | `/profile` | Return the loaded candidate profile |
| GET | `/score-cache/stats` | Show cache size and count |
| DELETE | `/score-cache` | Clear the cache (use after profile changes) |

**Your data stays on your machine.** All AI inference runs locally via Ollama. The only external call is to Google Sheets — your own account, via an OAuth2 app you created in your own Google Cloud project.
