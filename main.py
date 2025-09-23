#!/usr/bin/env python3
"""
Job Monitor System - Main Entry Point
"""

import argparse
import sys
from pathlib import Path

def run_streamlit():
    """Run Streamlit UI"""
    import streamlit.web.cli as stcli
    sys.argv = ["streamlit", "run", "ui/streamlit_app.py", "--server.port", "8501"]
    stcli.main()

def run_fastapi():
    """Run FastAPI backend"""
    import uvicorn
    from ui.backend_api import app
    uvicorn.run(app, host="0.0.0.0", port=8000)

def run_scheduler_only():
    """Run only the background scheduler"""
    from collector.scheduler import job_scheduler
    print("Starting job scheduler...")
    job_scheduler.start()
    
    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nShutting down scheduler...")
        job_scheduler.stop()

def setup_database():
    """Initialize database and vector store"""
    from collector.db import db_manager
    from analysis.vector_store import vector_store
    
    print("Setting up database...")
    # Database tables are created automatically in db_manager.__init__()
    
    print("Initializing vector store...")
    # Vector store is initialized automatically
    
    print("Database setup complete!")

def main():
    parser = argparse.ArgumentParser(description="Job Monitor System")
    parser.add_argument(
        'mode',
        choices=['streamlit', 'fastapi', 'scheduler', 'setup'],
        help='Run mode: streamlit (UI), fastapi (API server), scheduler (background only), or setup (initialize DB)'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'setup':
        setup_database()
    elif args.mode == 'streamlit':
        run_streamlit()
    elif args.mode == 'fastapi':
        run_fastapi()
    elif args.mode == 'scheduler':
        run_scheduler_only()

if __name__ == "__main__":
    main()