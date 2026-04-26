# utils/dependency_injection.py

"""
Jednostavan dependency injection container.
"""

import logging
from typing import Any, Dict, Type, Optional, Callable
from functools import wraps


logger = logging.getLogger(__name__)


class DIContainer:
    """
    Dependency Injection Container.
    
    Odgovornosti:
    - Registracija servisa
    - Razrješavanje zavisnosti
    - Lifecycle management
    - Scoping (singleton, transient)
    """
    
    def __init__(self):
        """Inicijalizacija DI containera."""
        self._services: Dict[str, Dict[str, Any]] = {}
        self._instances: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
    
    def register(self, 
                service_type: Type,
                implementation: Optional[Type] = None,
                scope: str = "singleton",
                factory: Optional[Callable] = None,
                **kwargs):
        """
        Registruj servis u container.
        
        Args:
            service_type: Tip servisa (interface ili abstract class)
            implementation: Konkretna implementacija (opciono ako je factory)
            scope: Scope servisa ('singleton' ili 'transient')
            factory: Factory funkcija za kreiranje instance (opciono)
            **kwargs: Dodatni parametri za factory
        """
        service_name = service_type.__name__
        
        if service_name in self._services:
            self.logger.warning(f"Servis {service_name} već registriran, overwriting")
        
        self._services[service_name] = {
            'type': service_type,
            'implementation': implementation,
            'scope': scope,
            'factory': factory,
            'factory_kwargs': kwargs
        }
        
        self.logger.debug(f"Registriran servis: {service_name} (scope: {scope})")
    
    def resolve(self, service_type: Type) -> Any:
        """
        Razriješi i vrati instancu servisa.
        
        Args:
            service_type: Tip servisa za razrješavanje
            
        Returns:
            Instanca servisa
            
        Raises:
            KeyError: Ako servis nije registriran
        """
        service_name = service_type.__name__
        
        if service_name not in self._services:
            raise KeyError(f"Servis {service_name} nije registriran")
        
        service_info = self._services[service_name]
        
        # Provjeri scope
        if service_info['scope'] == 'singleton':
            # Vrati postojeću instancu ili kreiraj novu
            if service_name not in self._instances:
                self._instances[service_name] = self._create_instance(service_info)
            return self._instances[service_name]
        
        elif service_info['scope'] == 'transient':
            # Uvijek kreiraj novu instancu
            return self._create_instance(service_info)
        
        else:
            raise ValueError(f"Nepoznat scope: {service_info['scope']}")
    
    def _create_instance(self, service_info: Dict[str, Any]) -> Any:
        """
        Kreiraj instancu servisa.
        
        Args:
            service_info: Informacije o servisu
            
        Returns:
            Kreirana instanca
        """
        if service_info['factory']:
            # Koristi factory funkciju
            instance = service_info['factory'](**service_info['factory_kwargs'])
        elif service_info['implementation']:
            # Kreiraj instancu implementacije
            implementation = service_info['implementation']
            
            # Provjeri da li implementacija ima dependency injection
            if hasattr(implementation, '__init__'):
                # Pokušaj automatski razriješiti dependency-je
                instance = self._create_with_dependencies(implementation)
            else:
                instance = implementation()
        else:
            # Kreiraj instancu direktno
            instance = service_info['type']()
        
        # Provjeri tip
        if not isinstance(instance, service_info['type']):
            raise TypeError(f"Instanca nije tipa {service_info['type'].__name__}")
        
        return instance
    
    def _create_with_dependencies(self, implementation: Type) -> Any:
        """
        Kreiraj instancu sa automatskim razrješavanjem dependency-ja.
        
        Args:
            implementation: Klasa za instanciranje
            
        Returns:
            Kreirana instanca
        """
        # Ova metoda bi trebala analizirati __init__ metodu
        # i automatski razriješiti dependency-je
        # Za sada, kreiraj instancu bez parametara
        return implementation()
    
    def register_singleton(self, service_type: Type, implementation: Type = None, **kwargs):
        """
        Registruj singleton servis.
        
        Args:
            service_type: Tip servisa
            implementation: Konkretna implementacija
            **kwargs: Dodatni parametri
        """
        self.register(
            service_type=service_type,
            implementation=implementation,
            scope='singleton',
            **kwargs
        )
    
    def register_transient(self, service_type: Type, implementation: Type = None, **kwargs):
        """
        Registruj transient servis.
        
        Args:
            service_type: Tip servisa
            implementation: Konkretna implementacija
            **kwargs: Dodatni parametri
        """
        self.register(
            service_type=service_type,
            implementation=implementation,
            scope='transient',
            **kwargs
        )
    
    def register_factory(self, service_type: Type, factory: Callable, scope: str = "singleton", **kwargs):
        """
        Registruj servis sa factory funkcijom.
        
        Args:
            service_type: Tip servisa
            factory: Factory funkcija
            scope: Scope servisa
            **kwargs: Dodatni parametri za factory
        """
        self.register(
            service_type=service_type,
            factory=factory,
            scope=scope,
            **kwargs
        )
    
    def has_service(self, service_type: Type) -> bool:
        """
        Provjeri da li je servis registriran.
        
        Args:
            service_type: Tip servisa
            
        Returns:
            True ako je registriran, False inače
        """
        return service_type.__name__ in self._services
    
    def clear(self):
        """Očisti sve registrovane servise."""
        self._services.clear()
        self._instances.clear()
        self.logger.info("DI container očišćen")
    
    def get_registered_services(self) -> Dict[str, Dict[str, Any]]:
        """
        Vrati listu registriranih servisa.
        
        Returns:
            Dictionary sa informacijama o servisima
        """
        return self._services.copy()
    
    def inject(self, service_type: Type):
        """
        Decorator za dependency injection.
        
        Args:
            service_type: Tip servisa za inject
            
        Returns:
            Decorator funkcija
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Razriješi servis
                service = self.resolve(service_type)
                
                # Dodaj servis u kwargs
                param_name = service_type.__name__.lower()
                kwargs[param_name] = service
                
                # Pozovi originalnu funkciju
                return func(*args, **kwargs)
            return wrapper
        return decorator


# Globalni DI container instance
_di_container_instance = None


def get_di_container() -> DIContainer:
    """
    Vrati globalni DI container (singleton).
    
    Returns:
        DIContainer instanca
    """
    global _di_container_instance
    if _di_container_instance is None:
        _di_container_instance = DIContainer()
    return _di_container_instance



# Utility funkcije
def inject_service(service_type: Type):
    """
    Decorator za dependency injection.
    
    Args:
        service_type: Tip servisa za inject
        
    Returns:
        Decorator funkcija
    """
    container = get_di_container()
    return container.inject(service_type)


def resolve_service(service_type: Type) -> Any:
    """
    Razriješi servis iz DI containera.
    
    Args:
        service_type: Tip servisa
        
    Returns:
        Instanca servisa
    """
    container = get_di_container()
    return container.resolve(service_type)


# Primjer korištenja:
"""
# U servisu:
from utils.dependency_injection import inject_service
from services.cache_service import CacheService

class MyService:
    @inject_service(CacheService)
    def __init__(self, cacheservice):
        self.cache = cacheservice
    
    def get_data(self):
        return self.cache.get('key')

# U controller-u:
from utils.dependency_injection import resolve_service
from services.my_service import MyService

class MyController:
    def __init__(self):
        self.service = resolve_service(MyService)
    
    def do_something(self):
        return self.service.get_data()
"""