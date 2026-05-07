"""
JobSpy microservice — FastAPI wrapper around python-jobspy.
Called by n8n via HTTP Request node.

Endpoints:
  GET  /health           — liveness probe
  POST /scrape           — single search; optionally writes CSV to /data/shared
  GET  /sources          — list supported job boards
  GET  /role-families    — return canonical role taxonomy
  GET  /files            — list CSVs written to /data/shared
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from jobspy import scrape_jobs
from pydantic import BaseModel, Field

app = FastAPI(
    title="JobSpy Service",
    description="Containerised job-board scraper for the Dublin BA/Data pipeline",
    version="1.1.0",
)

DEFAULT_SITES = ["indeed", "linkedin"]
ALL_SITES = ["indeed", "linkedin", "glassdoor", "zip_recruiter",
             "google", "naukri", "bayt"]

SHARED_DIR = Path("/data/shared")

GEO_TO_COUNTRY = {
    "ireland": "ireland",
    "dublin": "ireland",
    "united kingdom": "uk",
    "uk": "uk",
    "london": "uk",
    "netherlands": "netherlands",
    "amsterdam": "netherlands",
    "germany": "germany",
    "berlin": "germany",
    "france": "france",
    "paris": "france",
    "india": "india",
    "bangalore": "india",
    "mumbai": "india",
    "delhi": "india",
    "new delhi": "india",
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


class ScrapeRequest(BaseModel):
    search_term: str = Field(..., description="Job title to search")
    location: str = Field(..., description="Geo, e.g. 'Dublin, Ireland'")
    sites: List[str] = Field(
        default_factory=lambda: DEFAULT_SITES.copy(),
        description="Job boards. Defaults to Indeed + LinkedIn."
    )
    results_wanted: int = Field(30, ge=1, le=100)
    hours_old: int = Field(168, ge=1, le=720)
    country_indeed: Optional[str] = Field(None)
    role_family: Optional[str] = Field(None)
    save_csv: bool = Field(
        True,
        description="If true, persist a CSV to /data/shared and return its path."
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "jobspy-service"}


@app.get("/sources")
def sources():
    return {"default": DEFAULT_SITES, "all": ALL_SITES}


@app.get("/role-families")
def role_families():
    return ROLE_FAMILIES


@app.get("/files")
def list_files():
    """List CSVs already written to the shared volume."""
    if not SHARED_DIR.exists():
        return {"files": []}
    files = sorted(SHARED_DIR.glob("jobs_*.csv"), reverse=True)
    return {
        "files": [
            {
                "name": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            }
            for f in files
        ]
    }


@app.post("/scrape")
def scrape(req: ScrapeRequest):
    invalid = [s for s in req.sites if s not in ALL_SITES]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown sites: {invalid}. Valid: {ALL_SITES}"
        )

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
        raise HTTPException(
            status_code=502,
            detail=f"Scraper error: {str(e)[:300]}"
        )

    timestamp = datetime.utcnow().isoformat()
    base_response = {
        "search_term": req.search_term,
        "location": req.location,
        "sites_queried": req.sites,
        "role_family": req.role_family,
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