import requests
import feedparser
from typing import List, Dict, Optional
from config.config_loader import config_loader
from bs4 import BeautifulSoup
import time
import random
from analysis.llm_client import llm_client

class RSSClient:
    def __init__(self):
        self.provider = self._detect_provider()
        self.session = requests.Session()
        self._setup_auth()
    
    def _detect_provider(self):
        """Detect RSS reader provider from config"""
        # Check config.yaml first for explicit mode setting
        rss_mode = config_loader.config.get('rss_mode', 'auto')
        
        if rss_mode == 'direct':
            return 'direct'
        elif rss_mode == 'miniflux':
            return 'miniflux'
        elif rss_mode == 'freshrss':
            return 'freshrss'
        elif rss_mode == 'auto':
            # Auto-detect based on .env (existing logic)
            if config_loader.get_env('MINIFLUX_URL'):
                return 'miniflux'
            elif config_loader.get_env('FRESHRSS_URL'):
                return 'freshrss'
            else:
                return 'direct'
        else:
            return 'direct'  # Default fallback
    
    def _setup_auth(self):
        """Setup authentication for RSS reader API"""
        if self.provider == 'miniflux':
            token = config_loader.get_env('MINIFLUX_TOKEN')
            self.session.headers.update({'X-Auth-Token': token})
            self.base_url = config_loader.get_env('MINIFLUX_URL')
        elif self.provider == 'freshrss':
            self.base_url = config_loader.get_env('FRESHRSS_URL')
            self.auth = (
                config_loader.get_env('FRESHRSS_USERNAME'),
                config_loader.get_env('FRESHRSS_PASSWORD')
            )
    
    def fetch_entries(self) -> List[Dict]:
        """Fetch all job entries from configured feeds"""
        print(f"Fetching RSS entries using {self.provider} provider")
        if self.provider == 'direct':
            return self._fetch_direct()
        elif self.provider == 'miniflux':
            return self._fetch_miniflux()
        elif self.provider == 'freshrss':
            return self._fetch_freshrss()
    
    def _fetch_direct(self) -> List[Dict]:
        """Direct RSS feed fetching"""
        entries = []
        feeds = config_loader.config['rss_feeds']
        
        for feed_config in feeds:
            try:
                response = self.session.get(feed_config['url'], timeout=30)
                feed = feedparser.parse(response.content)
                
                # Collect all entries first without content
                batch_entries = []
                urls_to_fetch = []

                for entry in feed.entries:
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    if self._is_job_already_processed(title, link):
                        continue  # Skip already processed jobs
                    entry_data = {
                        'title': entry.get('title', ''),
                        'link': entry.get('link', ''),
                        'description': entry.get('description', ''),
                        'published': entry.get('published', ''),
                        'source': feed_config['name'],
                        'category': feed_config.get('category', 'general'),
                        'content': ''  # Will be filled later
                    }
                    batch_entries.append(entry_data)
                    urls_to_fetch.append(entry.get('link', ''))

                # Batch fetch all content
                content_results = self._fetch_full_content_batch(urls_to_fetch)

                # Assign content back to entries
                for entry_data in batch_entries:
                    entry_data['content'] = content_results.get(entry_data['link'], '')
                    entries.append(entry_data)
            except Exception as e:
                print(f"Error fetching {feed_config['name']}: {e}")
        
        return entries
    
    def _fetch_miniflux(self) -> List[Dict]:
        """Fetch from Miniflux API - only new/updated entries"""
        try:
            # Get entries since last fetch (store last fetch timestamp)
            last_fetch = config_loader.config.get('last_miniflux_fetch', None)
            
            params = {
                'limit': 1000,
                'order': 'published_at',
                'direction': 'desc'
            }
            
            # Add timestamp filter if we have a previous fetch time
            if last_fetch:
                params['after'] = last_fetch
            
            response = self.session.get(f"{self.base_url}/v1/entries", params=params)
            response.raise_for_status()
            data = response.json()
            
            entries = []
            latest_timestamp = last_fetch
            
            for entry in data.get('entries', []):
                title = entry.get('title', '')
                link = entry.get('url', '')
                if self._is_job_already_processed(title, link):
                    continue  # Skip already processed jobs

                # Track the latest timestamp we've seen
                entry_time = entry.get('published_at', '')
                if not latest_timestamp or entry_time > latest_timestamp:
                    latest_timestamp = entry_time
                
                # When checking relevance, get both result and score
                is_relevant, relevance_score = self._quick_relevance_check(entry.get('title', ''), entry.get('description', ''), entry.get('link', ''))
                # Skip content fetching for low-relevance jobs
                if not is_relevant:
                    continue
                elif relevance_score < 6:
                    continue  # Skip low-relevance jobs
                elif relevance_score >= 6:
                    entry['relevance_score'] = relevance_score
                
                entries.append({
                    'title': entry.get('title', ''),
                    'link': entry.get('url', ''),
                    'description': entry.get('content', ''),
                    'published': entry_time,
                    'source': entry.get('feed', {}).get('title', ''),
                    'category': 'general',
                    'content': self._fetch_full_content(entry.get('url', ''))  # Get full content
                })
            
            # Update last fetch timestamp in config
            if latest_timestamp and latest_timestamp != last_fetch:
                config = config_loader.config
                config['last_miniflux_fetch'] = latest_timestamp
                config_loader.save_yaml_config(config)
                print(f"Updated last fetch timestamp to: {latest_timestamp}")
            
            return entries
        except Exception as e:
            print(f"Error fetching from Miniflux: {e}")
            return []
    
    def _fetch_freshrss(self) -> List[Dict]:
        """Fetch from FreshRSS API"""
        try:
            params = {
                'output': 'json',
                'n': 1000,  # Number of items
            }
            response = self.session.get(
                f"{self.base_url}/reader/api/0/stream/contents/reading-list",
                params=params,
                auth=self.auth
            )
            response.raise_for_status()
            data = response.json()
            
            entries = []
            for item in data.get('items', []):
                entries.append({
                    'title': item.get('title', ''),
                    'link': item.get('canonical', [{}])[0].get('href', ''),
                    'description': item.get('summary', {}).get('content', ''),
                    'published': item.get('published', ''),
                    'source': item.get('origin', {}).get('title', ''),
                    'category': 'general',
                    'content': item.get('content', {}).get('content', '')
                })
            
            return entries
        except Exception as e:
            print(f"Error fetching from FreshRSS: {e}")
            return []
    
    def _fetch_full_content(self, url: str) -> str:
        """Fetch full content using multiple strategies"""
        if not url:
            return ""
        
        # Strategy 1: Try Jina Reader API first
        content = self._fetch_with_jina(url)
        if content:
            return content
        
        # Strategy 2: Fallback to enhanced BeautifulSoup
        content = self._fetch_with_enhanced_bs4(url)
        if content:
            return content
        
        # Strategy 3: Final fallback to basic extraction
        return self._fetch_basic_content(url)

    def _fetch_with_jina(self, url: str) -> str:
        """Use Jina Reader API for clean content extraction"""
        try:
            # Random delay between 1-3 seconds
            time.sleep(random.uniform(1.0, 3.0))
            print(f"Trying Jina Reader for {url}")  # Debug log
            jina_url = f"https://r.jina.ai/{url}"
            response = self.session.get(jina_url, timeout=30)
            if response.status_code == 200:
                return response.text[:8000]  # Increased limit for better content
        except Exception as e:
            print(f"Jina Reader failed for {url}: {e}")
        return ""

    def _fetch_with_enhanced_bs4(self, url: str) -> str:
        """Enhanced BeautifulSoup with better selectors"""
        try:
            response = self.session.get(url, timeout=30)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
                element.decompose()
            
            # Try to find main content areas (common job board patterns)
            content_selectors = [
                'main', '[role="main"]', '.job-description', '.job-details', 
                '.position-summary', '.content', '#content', '.post-content',
                'article', '.job-posting', '.job-info'
            ]
            
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    text = content_div.get_text(strip=True, separator='\n')
                    if len(text) > 200:  # Ensure we got substantial content
                        return text[:8000]
            
            # Fallback to body
            return soup.get_text(strip=True, separator='\n')[:8000]
            
        except Exception as e:
            print(f"Enhanced BS4 failed for {url}: {e}")
        return ""

    def _fetch_basic_content(self, url: str) -> str:
        """Your existing basic content extraction as final fallback"""
        try:
            response = self.session.get(url, timeout=30)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for script in soup(["script", "style"]):
                script.decompose()
            
            return soup.get_text(strip=True, separator='\n')[:5000]
        except Exception as e:
            print(f"Basic content extraction failed for {url}: {e}")
            return ""
        
    def _fetch_full_content_batch(self, urls: list) -> dict:
        results = {}
        batch_size = 5  # Process 5 URLs at a time
        
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            for url in batch:
                results[url] = self._fetch_full_content(url)
            
            # Pause between batches
            if i + batch_size < len(urls):
                time.sleep(10)  # 10 second pause between batches
        
        return results

    def sync_feeds_to_miniflux(self):
        """Sync feeds from config.yaml to Miniflux"""
        if self.provider != 'miniflux':
            return
        
        feeds_config = config_loader.config['rss_feeds']
        
        for feed_config in feeds_config:
            try:
                # Add feed to Miniflux via API
                data = {
                    "feed_url": feed_config['url'],
                    "category_title": feed_config.get('category', 'Jobs')
                }
                response = self.session.post(f"{self.base_url}/v1/feeds", json=data)
                if response.status_code == 201:
                    print(f"Added feed to Miniflux: {feed_config['name']}")
                elif response.status_code == 409:
                    print(f"Feed already exists in Miniflux: {feed_config['name']}")
                else:
                    print(f"Failed to add feed {feed_config['name']}: {response.status_code}")
            except Exception as e:
                print(f"Error syncing feed {feed_config['name']} to Miniflux: {e}")

    def reload_config(self):
        """Reload configuration and reinitialize provider"""
        config_loader._config = None  # Clear cached config
        self.provider = self._detect_provider()
        self._setup_auth()
        print(f"RSS client reloaded with provider: {self.provider}")

    def _quick_relevance_check(self, title: str, description: str, link: str = None) -> bool:
        """Quick LLM call using filter model to check job relevance and recruitment eligibility"""
        from analysis.llm_client import llm_client
        from collector.db import db_manager, JobEntry
        
        # Check cache if we have a link
        if link:
            job_id = db_manager.generate_job_id(title, link)
            cached = db_manager.session.query(JobEntry).filter_by(id=job_id).first()
            if cached and hasattr(cached, 'relevance_score') and cached.relevance_score > 0:
                return cached.relevance_score >= 6, cached.relevance_score

        filters = config_loader.config.get('recruitment_filters', {})
        degree_req = filters.get('required_degree', 'PhD')
        citizenship_req = filters.get('citizenship_requirement', 'open to international students')
        
        prompt = f"""Rate this job for {degree_req} international student (0-10):
    Keywords: {', '.join(config_loader.config['keywords'])}
    Requirements: {degree_req} degree, {citizenship_req}

    Title: {title}
    Description: {description}

    Check for: {degree_req} requirement, visa sponsorship, citizenship restrictions
    Score only (0-10):"""
        
        try:
            score = llm_client._call_llm(prompt)
            return int(score.strip()) >= 6, int(score.strip())
        except:
            return True, 6  # Default to relevant if LLM fails
        
    def _is_job_already_processed(self, title: str, link: str) -> bool:
        """Check if job already exists and is processed"""
        from collector.db import db_manager, JobEntry  # Import JobEntry explicitly
        job_id = db_manager.generate_job_id(title, link)
        existing = db_manager.session.query(JobEntry).filter_by(id=job_id).first()
        return existing is not None