# utils/cache.py

"""
Caching sistem za performance optimizaciju.
"""

import logging
import time
from typing import Any, Optional, Dict, Callable
from functools import wraps
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class CacheItem:
    """Jedna stavka u cache-u."""
    
    def __init__(self, value: Any, ttl: int = 300):
        """
        Inicijalizacija cache stavke.
        
        Args:
            value: Vrijednost za čuvanje
            ttl: Time to live u sekundama (default: 5 minuta)
        """
        self.value = value
        self.created_at = datetime.now()
        self.ttl = ttl
    
    def is_expired(self) -> bool:
        """Provjeri da li je stavka istekla."""
        if self.ttl <= 0:
            return False  # Beskonačan TTL
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl)
    
    def get_age(self) -> float:
        """Vrati starost stavke u sekundama."""
        return (datetime.now() - self.created_at).total_seconds()


class Cache:
    """
    Simple caching sistem sa TTL support-om.
    """
    
    def __init__(self, name: str = "default", max_size: int = 1000):
        """
        Inicijalizacija cache-a.
        
        Args:
            name: Ime cache-a (za logging)
            max_size: Maksimalan broj stavki
        """
        self.name = name
        self.max_size = max_size
        self._cache: Dict[str, CacheItem] = {}
        self.hits = 0
        self.misses = 0
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Dobavi vrijednost iz cache-a.
        
        Args:
            key: Ključ za pretragu
            default: Default vrijednost ako ključ ne postoji
            
        Returns:
            Vrijednost iz cache-a ili default
        """
        if key in self._cache:
            item = self._cache[key]
            if item.is_expired():
                # Izbriši isteklu stavku
                del self._cache[key]
                self.misses += 1
                return default
            self.hits += 1
            return item.value
        else:
            self.misses += 1
            return default
    
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        Postavi vrijednost u cache.
        
        Args:
            key: Ključ za čuvanje
            value: Vrijednost za čuvanje
            ttl: Time to live u sekundama
        """
        # Provjeri veličinu cache-a
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        # Postavi novu stavku
        self._cache[key] = CacheItem(value, ttl)
    
    def delete(self, key: str) -> bool:
        """
        Obriši stavku iz cache-a.
        
        Args:
            key: Ključ za brisanje
            
        Returns:
            True ako je obrisano, False ako nije postojalo
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Očisti sav cache."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0
    
    def _evict_oldest(self) -> None:
        """Izbaci najstariju stavku iz cache-a."""
        if not self._cache:
            return
        
        # Pronađi najstariju stavku
        oldest_key = None
        oldest_time = None
        
        for key, item in self._cache.items():
            if oldest_time is None or item.created_at < oldest_time:
                oldest_key = key
                oldest_time = item.created_at
        
        if oldest_key:
            del self._cache[oldest_key]
            self.logger.debug(f"Evicted oldest item: {oldest_key}")
    
    def cleanup(self) -> int:
        """
        Očisti istekle stavke iz cache-a.
        
        Returns:
            Broj obrisanih stavki
        """
        expired_keys = []
        
        for key, item in self._cache.items():
            if item.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired items")
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Vrati statistiku cache-a.
        
        Returns:
            Dictionary sa statistikom
        """
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0
        
        return {
            'name': self.name,
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.2%}",
            'total_requests': total_requests
        }
    
    def keys(self):
        """Vrati sve ključeve u cache-u."""
        return list(self._cache.keys())
    
    def values(self):
        """Vrati sve vrijednosti u cache-u."""
        return [item.value for item in self._cache.values() if not item.is_expired()]
    
    def items(self):
        """Vrati sve (key, value) parove u cache-u."""
        return [(k, item.value) for k, item in self._cache.items() if not item.is_expired()]


# Globalni cache instance
_cache_instances: Dict[str, Cache] = {}


def get_cache(name: str = "default", max_size: int = 1000) -> Cache:
    """
    Vrati cache instancu (singleton pattern).
    
    Args:
        name: Ime cache-a
        max_size: Maksimalan broj stavki
        
    Returns:
        Cache instanca
    """
    if name not in _cache_instances:
        _cache_instances[name] = Cache(name, max_size)
    return _cache_instances[name]


def cached(cache_name: str = "default", ttl: int = 300, key_func: Callable = None):
    """
    Decorator za caching rezultata funkcije.
    
    Args:
        cache_name: Ime cache-a za korištenje
        ttl: Time to live u sekundama
        key_func: Funkcija za generisanje cache key-a (opciono)
        
    Returns:
        Decorator funkcija
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generiši cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generacija
                key_parts = [func.__module__, func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = "_".join(key_parts)
            
            # Pokušaj dobiti iz cache-a
            cache = get_cache(cache_name)
            cached_value = cache.get(cache_key)
            
            if cached_value is not None:
                logger.debug(f"Cache hit: {func.__name__}")
                return cached_value
            
            # Izračunaj vrijednost
            logger.debug(f"Cache miss: {func.__name__}")
            result = func(*args, **kwargs)
            
            # Sačuvaj u cache
            cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


def clear_all_caches():
    """Očisti sve cache instance."""
    for cache in _cache_instances.values():
        cache.clear()
    _cache_instances.clear()


def get_all_cache_stats() -> Dict[str, Dict[str, Any]]:
    """
    Vrati statistiku za sve cache instance.
    
    Returns:
        Dictionary sa statistikom za svaki cache
    """
    stats = {}
    for name, cache in _cache_instances.items():
        stats[name] = cache.get_stats()
    return stats


# Specializovani cache-i za česte upite
def get_database_cache() -> Cache:
    """Vrati cache za database upite."""
    return get_cache("database", max_size=500)


def get_ui_cache() -> Cache:
    """Vrati cache za UI podatke."""
    return get_cache("ui", max_size=200)


def get_config_cache() -> Cache:
    """Vrati cache za konfiguraciju."""
    return get_cache("config", max_size=100)


# Utility funkcije za česte pattern-e
def cache_database_query(ttl: int = 60):
    """
    Decorator za caching database query-ja.
    
    Args:
        ttl: Time to live u sekundama
        
    Returns:
        Decorator funkcija
    """
    return cached(cache_name="database", ttl=ttl)


def cache_ui_data(ttl: int = 30):
    """
    Decorator za caching UI podataka.
    
    Args:
        ttl: Time to live u sekundama
        
    Returns:
        Decorator funkcija
    """
    return cached(cache_name="ui", ttl=ttl)


def cache_config_value(ttl: int = 300):
    """
    Decorator za caching konfiguracijskih vrijednosti.
    
    Args:
        ttl: Time to live u sekundama
        
    Returns:
        Decorator funkcija
    """
    return cached(cache_name="config", ttl=ttl)