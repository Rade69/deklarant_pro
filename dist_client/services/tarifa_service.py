import os as _os
import services.tariff.tarifa_service as _tarifa_mod

# Patch DB_PATH if the compiled .pyd resolved a wrong path (e.g. dist_client/database/)
if not _os.path.exists(_tarifa_mod.DB_PATH):
    _candidates = [
        _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..', 'database', 'deklarant_sistem.db')),
        _os.path.join('database', 'deklarant_sistem.db'),
    ]
    for _p in _candidates:
        if _os.path.exists(_p):
            _tarifa_mod.DB_PATH = _p
            _tarifa_mod._shared_conn = None
            # Obriši lru_cache koji je mogao keširati None dok DB nije bio dostupan
            if hasattr(_tarifa_mod.trazi_po_kodu, 'cache_clear'):
                _tarifa_mod.trazi_po_kodu.cache_clear()
            break

from services.tariff.tarifa_service import *  # noqa: F401, F403
from services.tariff import TarifaService  # noqa: F401
