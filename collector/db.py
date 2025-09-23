from sqlalchemy import create_engine, Column, String, Text, DateTime, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config.config_loader import config_loader
import hashlib

Base = declarative_base()

class JobEntry(Base):
    __tablename__ = 'job_entries'
    
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    link = Column(String, nullable=False)
    description = Column(Text)
    content = Column(Text)
    published = Column(String)
    source = Column(String)
    category = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    analyzed = Column(Boolean, default=False)
    analysis_result = Column(Text)  # JSON string of LLM analysis
    relevance_score = Column(Integer, default=0)  # Cache relevance check result

class DatabaseManager:
    def __init__(self):
        db_url = config_loader.get_env('DATABASE_URL', 'sqlite:///jobs.db')
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def generate_job_id(self, title: str, link: str) -> str:
        """Generate unique ID from title and link"""
        content = f"{title}|{link}".encode('utf-8')
        return hashlib.md5(content).hexdigest()
    
    def add_job_entry(self, entry_data: dict) -> bool:
        """Add job entry if not exists (deduplication)"""
        job_id = self.generate_job_id(entry_data['title'], entry_data['link'])
        
        existing = self.session.query(JobEntry).filter_by(id=job_id).first()
        if existing:
            return False  # Already exists
        
        job_entry = JobEntry(
            id=job_id,
            title=entry_data['title'],
            link=entry_data['link'],
            description=entry_data['description'],
            content=entry_data['content'],
            published=entry_data['published'],
            source=entry_data['source'],
            category=entry_data['category'],
            relevance_score=entry_data.get('relevance_score', 0)
        )
        
        self.session.add(job_entry)
        self.session.commit()
        return True
    
    def get_unanalyzed_entries(self):
        """Get entries that haven't been analyzed by LLM"""
        return self.session.query(JobEntry).filter_by(analyzed=False).all()
    
    def update_analysis_result(self, job_id: str, analysis_result: str):
        """Update job entry with LLM analysis result"""
        entry = self.session.query(JobEntry).filter_by(id=job_id).first()
        if entry:
            entry.analysis_result = analysis_result
            entry.analyzed = True
            self.session.commit()
    
    def get_all_entries(self, limit: int = 100, offset: int = 0):
        """Get all job entries with pagination"""
        return self.session.query(JobEntry).offset(offset).limit(limit).all()
    
    def search_entries(self, query: str, limit: int = 50):
        """Basic text search in titles and descriptions"""
        return self.session.query(JobEntry).filter(
            JobEntry.title.contains(query) | 
            JobEntry.description.contains(query)
        ).limit(limit).all()

db_manager = DatabaseManager()