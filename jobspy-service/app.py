"""
JobSpy microservice — FastAPI wrapper around python-jobspy + Ollama scoring.
Called by n8n via HTTP Request node.

Endpoints:
  GET  /health           — liveness probe
  POST /scrape           — single search; optionally writes CSV to /data/shared
  POST /score            — score a single job against the candidate profile
  POST /score-batch      — score many jobs in one request, with bounded concurrency
  GET  /sources          — list supported job boards
  GET  /role-families    — return canonical role taxonomy
  GET  /files            — list CSVs written to /data/shared
  GET  /profile          — return the candidate profile
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import httpx
import pandas as pd
from fastapi import FastAPI, HTTPException
from jobspy import scrape_jobs
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("jobspy")

app = FastAPI(
    title="JobSpy Service",
    description="Containerised job-board scraper + local LLM scoring for the Dublin BA/Data pipeline",
    version="3.0.0",
)

# ---------- CONFIG ----------

DEFAULT_SITES = ["indeed", "linkedin"]
ALL_SITES = ["indeed", "linkedin", "glassdoor", "zip_recruiter",
             "google", "naukri", "bayt"]

SHARED_DIR = Path("/data/shared")
PROFILE_PATH = Path(__file__).parent / "profile.json"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))
OLLAMA_CONCURRENCY = int(os.getenv("OLLAMA_CONCURRENCY", "3"))

GEO_TO_COUNTRY = {
    "ireland": "ireland", "dublin": "ireland",
    "united kingdom": "uk", "uk": "uk", "london": "uk",
    "netherlands": "netherlands", "amsterdam": "netherlands",
    "germany": "germany", "berlin": "germany",
    "france": "france", "paris": "france",
    "india": "india", "bangalore": "india", "mumbai": "india",
    "delhi": "india", "new delhi": "india",
}

ROLE_FAMILIES = {
    "BA": ["Business Analyst", "Senior Business Analyst", "Business Systems Analyst"],
    "Data": ["Data Analyst", "BI Analyst", "Reporting Analyst"],
    "CRM_Salesforce": ["Salesforce Administrator", "CRM Analyst", "Sales Operations Analyst"],
    "Systems": ["Systems Analyst", "Business Systems Integration"],
}


def infer_country(location: str) -> Optional[str]:
    if not location:
        return None
    loc_lower = location.lower()
    for key, country in GEO_TO_COUNTRY.items():
        if key in loc_lower:
            return country
    return None


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Profile file not found at {PROFILE_PATH}")
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- REQUEST/RESPONSE MODELS ----------

class ScrapeRequest(BaseModel):
    search_term: str
    location: str
    sites: List[str] = Field(default_factory=lambda: DEFAULT_SITES.copy())
    results_wanted: int = Field(30, ge=1, le=100)
    hours_old: int = Field(168, ge=1, le=720)
    country_indeed: Optional[str] = None
    role_family: Optional[str] = None
    save_csv: bool = True


class ScoreJob(BaseModel):
    title: str
    company: Optional[str] = ""
    location: Optional[str] = ""
    description: Optional[str] = ""
    job_url: Optional[str] = ""


class ScoreResult(BaseModel):
    job_url: str
    score: int = Field(..., ge=0, le=10)
    reason: str
    error: Optional[str] = None


class ScoreBatchRequest(BaseModel):
    jobs: List[ScoreJob]


class ScoreBatchResponse(BaseModel):
    results: List[ScoreResult]
    model: str
    total_seconds: float
    success_count: int
    error_count: int


# ---------- ENDPOINTS ----------

@app.get("/health")
def health():
    return {"status": "ok", "service": "jobspy-service", "version": "3.0.0"}


@app.get("/sources")
def sources():
    return {"default": DEFAULT_SITES, "all": ALL_SITES}


@app.get("/role-families")
def role_families():
    return ROLE_FAMILIES


@app.get("/profile")
def get_profile():
    return load_profile()


@app.get("/files")
def list_files():
    if not SHARED_DIR.exists():
        return {"files": []}
    files = sorted(SHARED_DIR.glob("jobs_*.csv"), reverse=True)
    return {
        "files": [
            {"name": f.name, "path": str(f), "size_bytes": f.stat().st_size,
             "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()}
            for f in files
        ]
    }


@app.post("/scrape")
def scrape(req: ScrapeRequest):
    invalid = [s for s in req.sites if s not in ALL_SITES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown sites: {invalid}")

    country = req.country_indeed or infer_country(req.location)

    try:
        df = scrape_jobs(
            site_name=req.sites,
            search_term=req.search_term,
            location=req.location,
            results_wanted=req.results_wanted,
            hours_old=req.hours_old,
            country_indeed=country,
            description_format="markdown",
            verbose=0,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scraper error: {str(e)[:300]}")

    timestamp = datetime.utcnow().isoformat()
    base_response = {
        "search_term": req.search_term, "location": req.location,
        "sites_queried": req.sites, "role_family": req.role_family,
        "scraped_at": timestamp,
    }

    if df is None or df.empty:
        return {**base_response, "count": 0, "jobs": [], "csv_path": None}

    df["search_term"] = req.search_term
    df["geo_searched"] = req.location
    if req.role_family:
        df["role_family"] = req.role_family

    csv_path = None
    if req.save_csv:
        SHARED_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        family_tag = (req.role_family or "all").lower()
        filename = f"jobs_{family_tag}_{ts}.csv"
        csv_path = str(SHARED_DIR / filename)
        df.to_csv(csv_path, index=False)

    df = df.where(pd.notnull(df), None)
    return {
        **base_response,
        "count": len(df),
        "csv_path": csv_path,
        "jobs": df.to_dict(orient="records"),
    }


# ---------- SCORING ----------

SCORING_PROMPT = """You are a strict, experienced career advisor scoring how well a job posting fits a specific candidate.

CANDIDATE PROFILE (JSON):
{profile}

JOB POSTING:
Title: {title}
Company: {company}
Location: {location}
Description: {description}

Score this job 0-10 for fit, where:
- 10 = excellent fit on role, level, location, skills, and industry preference
- 7-9 = strong fit with minor gaps
- 4-6 = partial fit, would require stretch
- 1-3 = weak fit, mostly mismatched
- 0 = explicit avoid (industry, role type, or seniority outside scope)

Consider:
- Is the job title within the candidate's preferred or acceptable target roles?
- Does the seniority match (avoid junior roles for a senior candidate)?
- Is it in their target geos or remote-friendly?
- Do the required skills overlap with their core skills?
- Is the industry preferred, neutral, or in their avoid list?

Respond ONLY with valid JSON in this exact format, nothing else:
{{"score": <integer 0-10>, "reason": "<one short sentence, max 25 words>"}}
"""


def build_prompt(profile: dict, job: ScoreJob) -> str:
    description = (job.description or "")[:1500]
    return SCORING_PROMPT.format(
        profile=json.dumps(profile, indent=2),
        title=job.title or "",
        company=job.company or "",
        location=job.location or "",
        description=description,
    )


def parse_score(raw: str) -> dict:
    match = re.search(r"\{.*?\}", raw, re.DOTALL)
    if not match:
        return {"score": 0, "reason": f"Parse error — no JSON: {raw[:80]}"}
    try:
        data = json.loads(match.group(0))
        score = int(data.get("score", 0))
        score = max(0, min(10, score))
        reason = str(data.get("reason", ""))[:200]
        return {"score": score, "reason": reason}
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return {"score": 0, "reason": f"Parse error: {str(e)[:80]}"}


def call_ollama_sync(prompt: str) -> str:
    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            r = client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.2}},
            )
            r.raise_for_status()
            return r.json().get("response", "")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {str(e)[:300]}")


async def call_ollama_async(client: httpx.AsyncClient, prompt: str) -> str:
    r = await client.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
              "options": {"temperature": 0.2}},
    )
    r.raise_for_status()
    return r.json().get("response", "")


@app.post("/score")
def score(req: ScoreJob):
    profile = load_profile()
    prompt = build_prompt(profile, req)
    raw = call_ollama_sync(prompt)
    parsed = parse_score(raw)
    return {**parsed, "model": OLLAMA_MODEL}

# ---------- SCORE CACHE ----------

CACHE_PATH = Path("/data/shared/score_cache.json")
CACHE_LOCK = asyncio.Lock()  # serialise writes
CACHE_FLUSH_EVERY = 25  # save to disk every N new scores


def load_cache() -> dict:
    """Load score cache from disk; tolerate missing or corrupt files."""
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"Cache corrupt or unreadable, starting fresh: {e}")
        return {}


def save_cache(cache: dict) -> None:
    """Save cache to disk atomically (write to temp, rename)."""
    tmp = CACHE_PATH.with_suffix(".json.tmp")
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        tmp.replace(CACHE_PATH)
    except OSError as e:
        log.error(f"Failed to save cache: {e}")


@app.get("/score-cache/stats")
def score_cache_stats():
    """Inspect the score cache."""
    cache = load_cache()
    return {
        "cached_count": len(cache),
        "path": str(CACHE_PATH),
        "size_bytes": CACHE_PATH.stat().st_size if CACHE_PATH.exists() else 0,
    }


@app.delete("/score-cache")
def score_cache_clear():
    """Clear the score cache (for testing or after profile changes)."""
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()
        return {"deleted": True, "path": str(CACHE_PATH)}
    return {"deleted": False, "reason": "no cache file"}


@app.post("/score-batch", response_model=ScoreBatchResponse)
async def score_batch(req: ScoreBatchRequest):
    """
    Score many jobs in one request. Bounded concurrency via asyncio.Semaphore.
    Results are cached to disk by job_url so re-runs are near-instant for
    already-scored jobs. Cache survives container restarts and crashes.
    """
    profile = load_profile()
    started = datetime.utcnow()
    cache = load_cache()
    semaphore = asyncio.Semaphore(OLLAMA_CONCURRENCY)

    # Partition input: cache hits vs jobs needing scoring
    results_by_url = {}
    to_score = []
    for job in req.jobs:
        url = job.job_url or ""
        if url and url in cache:
            cached = cache[url]
            results_by_url[url] = ScoreResult(
                job_url=url,
                score=cached["score"],
                reason=cached["reason"],
                error=None,
            )
        else:
            to_score.append(job)

    cache_hits = len(results_by_url)
    log.info(
        f"score-batch: {len(req.jobs)} input, {cache_hits} cached, "
        f"{len(to_score)} to score, concurrency={OLLAMA_CONCURRENCY}"
    )

    new_scores_since_flush = 0

    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:

        async def score_one(idx: int, job: ScoreJob) -> ScoreResult:
            nonlocal new_scores_since_flush
            async with semaphore:
                try:
                    prompt = build_prompt(profile, job)
                    raw = await call_ollama_async(client, prompt)
                    parsed = parse_score(raw)
                    result = ScoreResult(
                        job_url=job.job_url or "",
                        score=parsed["score"],
                        reason=parsed["reason"],
                        error=None,
                    )

                    # Update cache (under lock to avoid concurrent writes)
                    if job.job_url:
                        async with CACHE_LOCK:
                            cache[job.job_url] = {
                                "score": parsed["score"],
                                "reason": parsed["reason"],
                                "scored_at": datetime.utcnow().isoformat(),
                                "model": OLLAMA_MODEL,
                            }
                            new_scores_since_flush += 1
                            if new_scores_since_flush >= CACHE_FLUSH_EVERY:
                                save_cache(cache)
                                new_scores_since_flush = 0

                    if (idx + 1) % 10 == 0 or idx == len(to_score) - 1:
                        log.info(f"score-batch: {idx + 1}/{len(to_score)} new scored")
                    return result

                except Exception as e:
                    log.warning(f"score-batch item {idx} failed: {str(e)[:200]}")
                    return ScoreResult(
                        job_url=job.job_url or "",
                        score=0,
                        reason="Scoring failed — see error",
                        error=str(e)[:300],
                    )

        new_results = await asyncio.gather(
            *[score_one(i, j) for i, j in enumerate(to_score)],
        )

    # Final cache flush
    async with CACHE_LOCK:
        if new_scores_since_flush > 0:
            save_cache(cache)

    # Combine cached + new results, preserving input order
    for r in new_results:
        if r.job_url:
            results_by_url[r.job_url] = r

    ordered_results = [
        results_by_url.get(j.job_url or "", ScoreResult(
            job_url=j.job_url or "",
            score=0,
            reason="No result returned",
            error="missing_result",
        ))
        for j in req.jobs
    ]

    elapsed = (datetime.utcnow() - started).total_seconds()
    success_count = sum(1 for r in ordered_results if r.error is None)
    error_count = len(ordered_results) - success_count
    log.info(
        f"score-batch: done in {elapsed:.1f}s — "
        f"{success_count} ok ({cache_hits} from cache), {error_count} errors"
    )

    return ScoreBatchResponse(
        results=ordered_results,
        model=OLLAMA_MODEL,
        total_seconds=round(elapsed, 1),
        success_count=success_count,
        error_count=error_count,
    )