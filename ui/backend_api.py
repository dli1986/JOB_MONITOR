from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from collector.db import db_manager, JobEntry
from analysis.vector_store import vector_store
from collector.scheduler import job_scheduler
from config.config_loader import config_loader

app = FastAPI(title="Job Monitor API", version="1.0.0")

# CORS middleware for Vue.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class JobResponse(BaseModel):
    id: str
    title: str
    link: str
    description: str
    source: str
    published: str
    analyzed: bool
    analysis_result: Optional[str] = None

class SearchRequest(BaseModel):
    query: str
    time_filter: Optional[str] = None
    max_results: int = 10

class FeedConfig(BaseModel):
    name: str
    url: str
    category: str = "academic"

class ConfigUpdate(BaseModel):
    feeds: Optional[List[FeedConfig]] = None
    keywords: Optional[List[str]] = None

# API Routes
@app.get("/")
async def root():
    return {"message": "Job Monitor API is running"}

@app.get("/api/jobs", response_model=List[JobResponse])
async def get_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None)
):
    """Get job entries with pagination and optional search"""
    try:
        if search:
            jobs = db_manager.search_entries(search, limit)
        else:
            jobs = db_manager.get_all_entries(limit, offset)
        
        return [job_to_response(job) for job in jobs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search", response_model=List[Dict[str, Any]])
async def semantic_search(request: SearchRequest):
    """Perform semantic search on job entries"""
    try:
        results = vector_store.semantic_search(
            request.query, 
            request.time_filter
        )
        return results[:request.max_results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/job/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get specific job entry by ID"""
    job = db_manager.session.query(JobEntry).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_to_response(job)

@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    total_jobs = len(db_manager.get_all_entries(limit=10000))
    unanalyzed_jobs = len(db_manager.get_unanalyzed_entries())
    
    return {
        "total_jobs": total_jobs,
        "analyzed_jobs": total_jobs - unanalyzed_jobs,
        "pending_analysis": unanalyzed_jobs
    }

@app.get("/api/config")
async def get_config():
    """Get current configuration"""
    return {
        "feeds": config_loader.config.get('rss_feeds', []),
        "keywords": config_loader.config.get('keywords', []),
        "scheduler": config_loader.config.get('scheduler', {}),
        "llm": config_loader.config.get('llm', {})
    }

@app.post("/api/config")
async def update_config(config_update: ConfigUpdate):
    """Update system configuration"""
    try:
        if config_update.feeds is not None:
            feeds = [feed.dict() for feed in config_update.feeds]
            config_loader.update_feeds(feeds)
        
        if config_update.keywords is not None:
            config_loader.update_keywords(config_update.keywords)
        
        return {"message": "Configuration updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/actions/fetch")
async def force_fetch():
    """Force immediate job fetching and analysis"""
    try:
        job_scheduler.fetch_and_analyze_jobs()
        return {"message": "Jobs fetched and queued for analysis"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/actions/analyze")
async def analyze_pending():
    """Analyze pending jobs"""
    try:
        job_scheduler.analyze_pending_jobs()
        return {"message": "Pending jobs analyzed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/actions/rebuild-index")
async def rebuild_index():
    """Rebuild vector search index"""
    try:
        vector_store.rebuild_index()
        return {"message": "Vector index rebuilt successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/actions/send-digest")
async def send_manual_digest(hours_back: int = 24):
    """Manually trigger email digest"""
    try:
        from ui.email_digest import email_digest
        success = email_digest.send_manual_digest(hours_back)
        if success:
            return {"message": f"Digest sent for last {hours_back} hours"}
        else:
            return {"message": "No jobs to send or email not configured"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
def job_to_response(job: JobEntry) -> JobResponse:
    """Convert database job entry to API response"""
    return JobResponse(
        id=job.id,
        title=job.title,
        link=job.link,
        description=job.description,
        source=job.source,
        published=job.published,
        analyzed=job.analyzed,
        analysis_result=job.analysis_result
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    """Start background scheduler"""
    job_scheduler.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)