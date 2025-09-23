import schedule
import time
from threading import Thread
from datetime import datetime
from collector.rss_client import RSSClient
from collector.db import db_manager
from analysis.llm_client import llm_client
from ui.email_digest import send_daily_digest
from config.config_loader import config_loader

class JobScheduler:
    def __init__(self):
        self.rss_client = RSSClient()
        self.running = False
    
    def start(self):
        """Start the scheduler in a background thread"""
        if self.running:
            return
        
        self.running = True
        config = config_loader.config
        
        # Schedule RSS fetching
        fetch_interval = config['scheduler']['fetch_interval_hours']
        schedule.every(fetch_interval).hours.do(self.fetch_and_analyze_jobs)
        
        # Schedule daily digest
        if config['ui']['enable_email_digest']:
            digest_time = config['scheduler']['digest_time']
            schedule.every().day.at(digest_time).do(send_daily_digest)
        
        # Run initial fetch
        self.fetch_and_analyze_jobs()
        
        # Start scheduler thread
        scheduler_thread = Thread(target=self._run_scheduler, daemon=True)
        scheduler_thread.start()
        print("Job scheduler started successfully")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def fetch_and_analyze_jobs(self):
        """Fetch RSS entries and analyze with LLM"""
        print(f"Fetching jobs at {datetime.now()}")
        
        try:
            # Reload config to get any keyword changes
            config_loader.reload_config()

            # Reload RSS client config in case mode was changed
            self.rss_client.reload_config()

            # Sync feeds to Miniflux if using Miniflux
            if self.rss_client.provider == 'miniflux':
                self.rss_client.sync_feeds_to_miniflux()
            
            # Fetch new entries
            entries = self.rss_client.fetch_entries()
            new_count = 0
            
            for entry in entries:
                if db_manager.add_job_entry(entry):
                    new_count += 1
            
            print(f"Added {new_count} new job entries")
            
            # Analyze unanalyzed entries (this will now also add to vector store)
            self.analyze_pending_jobs()
            
        except Exception as e:
            print(f"Error in scheduled job fetch: {e}")
    
    def analyze_pending_jobs(self):
        """Analyze jobs that haven't been processed by LLM"""
        from analysis.vector_store import vector_store  # Import here to avoid circular import
        
        unanalyzed = db_manager.get_unanalyzed_entries()
        analyzed_jobs = []
        
        for job in unanalyzed:
            try:
                analysis = llm_client.analyze_job_posting(job)
                db_manager.update_analysis_result(job.id, analysis)
                analyzed_jobs.append(job)  # Collect analyzed jobs
                print(f"Analyzed job: {job.title}")
            except Exception as e:
                print(f"Error analyzing job {job.id}: {e}")
        
        # Add analyzed jobs to vector store
        if analyzed_jobs:
            try:
                vector_store.add_job_entries(analyzed_jobs)
                print(f"Added {len(analyzed_jobs)} jobs to vector store")
            except Exception as e:
                print(f"Error adding jobs to vector store: {e}")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        schedule.clear()

job_scheduler = JobScheduler()