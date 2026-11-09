"""
Scraper Factory - Manages and creates price scrapers
"""
import logging
from typing import Dict, Type, Optional
from app.services.hupx_scraper import BasePriceScraper, HUPXScraper, MEMOScraper, ExampleScraper

logger = logging.getLogger(__name__)


class ScraperFactory:
    """Factory class to create and manage price scrapers"""
    
    # Registry of available scrapers
    _scrapers: Dict[str, Type[BasePriceScraper]] = {
        'hupx': HUPXScraper,
        'memo': MEMOScraper,
        'example': ExampleScraper,
    }
    
    # Cache of instantiated scrapers
    _instances: Dict[str, BasePriceScraper] = {}
    
    @classmethod
    def register_scraper(cls, name: str, scraper_class: Type[BasePriceScraper]):
        """
        Register a new scraper class.
        
        Args:
            name: Unique name for the scraper (e.g., 'my_custom_scraper')
            scraper_class: Class that inherits from BasePriceScraper
        """
        if not issubclass(scraper_class, BasePriceScraper):
            raise ValueError(f"Scraper class must inherit from BasePriceScraper")
        
        cls._scrapers[name] = scraper_class
        logger.info(f"Registered scraper: {name}")
    
    @classmethod
    def get_scraper(cls, name: Optional[str] = None) -> BasePriceScraper:
        """
        Get a scraper instance by name.
        Uses singleton pattern - returns the same instance if already created.
        
        Args:
            name: Name of the scraper (default: 'hupx')
        
        Returns:
            Instance of the requested scraper
        """
        if name is None:
            name = 'hupx'  # Default scraper
        
        if name not in cls._scrapers:
            available = ', '.join(cls._scrapers.keys())
            raise ValueError(f"Scraper '{name}' not found. Available scrapers: {available}")
        
        # Return cached instance if exists
        if name in cls._instances:
            return cls._instances[name]
        
        # Create new instance
        scraper_class = cls._scrapers[name]
        instance = scraper_class()
        cls._instances[name] = instance
        
        logger.info(f"Created scraper instance: {name}")
        return instance
    
    @classmethod
    def list_scrapers(cls) -> Dict[str, str]:
        """
        List all available scrapers.
        
        Returns:
            Dictionary mapping scraper names to their class names
        """
        return {
            name: scraper_class.__name__
            for name, scraper_class in cls._scrapers.items()
        }
    
    @classmethod
    def get_default_scraper(cls) -> BasePriceScraper:
        """Get the default scraper (HUPX)"""
        return cls.get_scraper('hupx')
