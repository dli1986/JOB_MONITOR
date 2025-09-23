import json
import requests
from typing import Dict, Any
from config.config_loader import config_loader
from analysis.prompt_templates import prompt_templates

class LLMClient:
    def __init__(self):
        self.config = config_loader.config['llm']
        self.provider = self.config['provider']
    
    def analyze_job_posting(self, job_entry) -> str:
        """Analyze job posting with LLM and return structured markdown"""
        keywords = config_loader.config['keywords']
        prompt = prompt_templates.get_job_analysis_prompt(
            job_entry.title, 
            job_entry.source,
            job_entry.published,
            job_entry.link,
            job_entry.category,
            job_entry.description,
            job_entry.content,
            keywords
        )
        
        response = self._call_llm(prompt)
        return response
    
    def generate_search_terms(self, user_query: str) -> list:
        """Generate search terms for semantic search"""
        prompt = prompt_templates.get_search_query_prompt(user_query)
        response = self._call_llm(prompt)
        
        # Extract search terms from response
        lines = response.strip().split('\n')
        terms = []
        for line in lines:
            if line.strip() and not line.startswith('Search Terms:'):
                terms.append(line.strip('- ').strip())
        
        return terms[:5]  # Return top 5 terms
    
    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider"""
        if self.provider == 'ollama':
            return self._call_ollama(prompt)
        elif self.provider == 'openai':
            return self._call_openai(prompt)
        elif self.provider == 'anthropic':
            return self._call_anthropic(prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama local API"""
        url = "http://localhost:11434/api/generate"
        data = {
            "model": self.config['model'],
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config['temperature'],
                "num_predict": self.config['max_tokens']
            }
        }
        
        try:
            response = requests.post(url, json=data, timeout=60)
            response.raise_for_status()
            return response.json()['response']
        except Exception as e:
            return f"Error calling Ollama: {e}"
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        import openai
        
        openai.api_key = config_loader.get_env('OPENAI_API_KEY')
        
        try:
            response = openai.ChatCompletion.create(
                model=self.config['model'],
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config['temperature'],
                max_tokens=self.config['max_tokens']
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error calling OpenAI: {e}"
    
    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API"""
        import anthropic
        
        client = anthropic.Anthropic(
            api_key=config_loader.get_env('ANTHROPIC_API_KEY')
        )
        
        try:
            response = client.messages.create(
                model=self.config['model'],
                max_tokens=self.config['max_tokens'],
                temperature=self.config['temperature'],
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error calling Anthropic: {e}"

llm_client = LLMClient()