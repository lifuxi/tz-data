"""
Data source manager.
Factory pattern for creating and managing data source instances.
"""
import logging
from typing import Optional, Type
from tzdata_pkg.maintenance.sources.base_source import BaseDataSource

logger = logging.getLogger(__name__)


class SourceManager:
    """Factory and registry for data sources."""
    
    # Registry of available source classes
    _source_registry: dict[str, Type[BaseDataSource]] = {}
    
    # Cache of instantiated sources
    _source_cache: dict[str, BaseDataSource] = {}
    
    @classmethod
    def register_source(cls, source_name: str, source_class: Type[BaseDataSource]):
        """
        Register a data source class.
        
        Args:
            source_name: Name of the data source (e.g., 'tushare', 'cffex')
            source_class: Data source class (must inherit from BaseDataSource)
        """
        cls._source_registry[source_name.lower()] = source_class
        logger.info(f"Registered data source: {source_name} -> {source_class.__name__}")
    
    @classmethod
    def get_source(
        cls,
        source_name: str,
        config: Optional[dict] = None,
        force_new: bool = False
    ) -> Optional[BaseDataSource]:
        """
        Get or create a data source instance.
        
        Args:
            source_name: Name of the data source
            config: Configuration dictionary for the source
            force_new: If True, create a new instance instead of using cache
        
        Returns:
            Data source instance, or None if not found
        """
        source_key = source_name.lower()
        
        # Check cache first (unless force_new)
        if not force_new and source_key in cls._source_cache:
            return cls._source_cache[source_key]
        
        # Find the source class
        source_class = cls._source_registry.get(source_key)
        
        if not source_class:
            logger.error(f"Unknown data source: {source_name}")
            return None
        
        try:
            # Create instance
            if config is None:
                config = cls._get_default_config(source_key)
            
            source_instance = source_class(config=config)
            
            # Validate credentials
            if not source_instance.validate_credentials():
                logger.warning(f"Invalid credentials for source: {source_name}")
                return None
            
            # Cache the instance
            cls._source_cache[source_key] = source_instance
            
            logger.info(f"Created data source instance: {source_name}")
            return source_instance
            
        except Exception as e:
            logger.error(f"Failed to create data source '{source_name}': {e}")
            return None
    
    @classmethod
    def _get_default_config(cls, source_name: str) -> dict:
        """
        Get default configuration for a data source.
        
        Args:
            source_name: Name of the data source
        
        Returns:
            Default configuration dictionary
        """
        # In production, load from environment variables or config file
        configs = {
            'tushare': {
                'token': ''  # Should be set via environment variable
            },
            'cffex': {},
            'shfe': {},
        }
        
        return configs.get(source_name, {})
    
    @classmethod
    def list_available_sources(cls) -> list[str]:
        """
        List all registered data sources.
        
        Returns:
            List of source names
        """
        return list(cls._source_registry.keys())
    
    @classmethod
    def clear_cache(cls):
        """Clear the source instance cache."""
        cls._source_cache.clear()
        logger.info("Cleared data source cache")


# Auto-register built-in sources
def _register_builtin_sources():
    """Register all built-in data sources."""
    try:
        from tzdata_pkg.maintenance.sources.tushare_source import TushareSource
        SourceManager.register_source('tushare', TushareSource)
        logger.info("Registered built-in source: TushareSource")
    except ImportError as e:
        logger.warning(f"Could not register TushareSource: {e}")

    # Register CFFEX and SHFE official sources
    try:
        from tzdata_pkg.maintenance.sources.cffex_source import CFFEXSource
        SourceManager.register_source('cffex', CFFEXSource)
        logger.info("Registered built-in source: CFFEXSource")
    except ImportError as e:
        logger.warning(f"Could not register CFFEXSource: {e}")

    try:
        from tzdata_pkg.maintenance.sources.shfe_source import SHFESource
        SourceManager.register_source('shfe', SHFESource)
        logger.info("Registered built-in source: SHFESource")
    except ImportError as e:
        logger.warning(f"Could not register SHFESource: {e}")

    # Add more sources here as they are implemented
    # from tzdata_pkg.maintenance.sources.dce_source import DCESource
    # SourceManager.register_source('dce', DCESource)
    # from tzdata_pkg.maintenance.sources.czce_source import CZCESource
    # SourceManager.register_source('czce', CZCESource)

# Register sources on module import
_register_builtin_sources()
