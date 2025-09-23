import json
import numpy as np
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
import faiss
from pathlib import Path
from collector.db import db_manager
from config.config_loader import config_loader

class VectorStore:
    def __init__(self):
        self.config = config_loader.config['vector_store']
        self.embedding_model = SentenceTransformer(self.config['embedding_model'])
        self.index = None
        self.documents = []
        self.index_path = Path("vector_index.faiss")
        self.docs_path = Path("documents.json")
        
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """Load existing index or create new one"""
        if self.index_path.exists() and self.docs_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.docs_path, 'r', encoding='utf-8') as f:
                    self.documents = json.load(f)
                print(f"Loaded vector index with {len(self.documents)} documents")
            except Exception as e:
                print(f"Error loading index: {e}")
                self._create_new_index()
        else:
            self._create_new_index()
    
    def _create_new_index(self):
        """Create new FAISS index"""
        # Create empty index with embedding dimension
        sample_embedding = self.embedding_model.encode(["sample text"])
        dimension = sample_embedding.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
        self.documents = []
    
    def add_job_entries(self, job_entries: List) -> None:
        """Add job entries to vector store"""
        if not job_entries:
            return
        
        new_docs = []
        texts_to_embed = []
        
        for job in job_entries:
            # Create searchable text combining title, description, and analysis
            analysis_text = ""
            if job.analysis_result:
                analysis_text = job.analysis_result
            
            searchable_text = f"{job.title} {job.description} {analysis_text}"
            
            doc = {
                'id': job.id,
                'title': job.title,
                'link': job.link,
                'source': job.source,
                'published': job.published,
                'text': searchable_text,
                'analysis': job.analysis_result
            }
            
            new_docs.append(doc)
            texts_to_embed.append(searchable_text)
        
        # Generate embeddings
        embeddings = self.embedding_model.encode(texts_to_embed)
        
        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Add to index
        self.index.add(embeddings.astype('float32'))
        self.documents.extend(new_docs)
        
        # Save index and documents
        self._save_index()
        print(f"Added {len(new_docs)} documents to vector store")
    
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search for similar job entries"""
        if self.index.ntotal == 0:
            return []
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query])
        faiss.normalize_L2(query_embedding)
        
        # Search
        scores, indices = self.index.search(query_embedding.astype('float32'), top_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.documents):
                doc = self.documents[idx].copy()
                doc['similarity_score'] = float(score)
                results.append(doc)
        
        return results
    
    def semantic_search(self, user_query: str, time_filter: str = None) -> List[Dict]:
        """Perform semantic search with optional time filtering"""
        from analysis.llm_client import llm_client
        
        # Generate search terms using LLM
        search_terms = llm_client.generate_search_terms(user_query)
        
        # Combine original query with generated terms
        enhanced_query = f"{user_query} {' '.join(search_terms)}"
        
        # Perform vector search
        results = self.search(enhanced_query, top_k=20)
        
        # Apply time filtering if specified
        if time_filter:
            results = self._apply_time_filter(results, time_filter)
        
        return results[:10]  # Return top 10 results
    
    def _apply_time_filter(self, results: List[Dict], time_filter: str) -> List[Dict]:
        """Apply time-based filtering to search results"""
        from datetime import datetime, timedelta
        import dateutil.parser
        
        now = datetime.now()
        
        if "3 months" in time_filter:
            cutoff = now - timedelta(days=90)
        elif "6 months" in time_filter:
            cutoff = now - timedelta(days=180)
        elif "1 year" in time_filter:
            cutoff = now - timedelta(days=365)
        else:
            return results
        
        filtered = []
        for result in results:
            try:
                published_date = dateutil.parser.parse(result.get('published', ''))
                if published_date.replace(tzinfo=None) >= cutoff:
                    filtered.append(result)
            except:
                # If can't parse date, include in results
                filtered.append(result)
        
        return filtered
    
    def _save_index(self):
        """Save FAISS index and documents to disk"""
        try:
            faiss.write_index(self.index, str(self.index_path))
            with open(self.docs_path, 'w', encoding='utf-8') as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving index: {e}")
    
    def rebuild_index(self):
        """Rebuild the entire index from database"""
        from collector.db import JobEntry
        print("Rebuilding vector index...")
        
        # Clear existing index
        self._create_new_index()
        
        # Get all analyzed job entries
        all_jobs = db_manager.session.query(db_manager.JobEntry).filter_by(analyzed=True).all()
        
        # Add to vector store in batches
        batch_size = 100
        for i in range(0, len(all_jobs), batch_size):
            batch = all_jobs[i:i + batch_size]
            self.add_job_entries(batch)
        
        print(f"Rebuilt index with {len(all_jobs)} documents")

vector_store = VectorStore()