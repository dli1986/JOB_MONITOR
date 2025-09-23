import os
import yaml
from dotenv import load_dotenv
from pathlib import Path

class ConfigLoader:
    def __init__(self):
        load_dotenv()
        self.config_path = Path("config.yaml")
        self._config = None
    
    @property
    def config(self):
        if self._config is None:
            self._config = self.load_yaml_config()
        return self._config
    
    def load_yaml_config(self):
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def save_yaml_config(self, config):
        """Save configuration to YAML file"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
        self._config = config
    
    def get_env(self, key, default=None):
        """Get environment variable"""
        return os.getenv(key, default)
    
    def update_feeds(self, feeds):
        """Update RSS feeds in config"""
        config = self.config.copy()
        config['rss_feeds'] = feeds
        self.save_yaml_config(config)
    
    def update_keywords(self, keywords):
        """Update keywords in config"""
        config = self.config.copy()
        config['keywords'] = keywords
        self.save_yaml_config(config)

    def reload_config(self):
        """Reload configuration from file"""
        self._config = None
        return self.config

# Global config instance
config_loader = ConfigLoader()