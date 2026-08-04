"""
Backup Service — database info.

TASK 10: Pojednostavljeno — samo get_database_size() je u upotrebi.
"""

import logging
from pathlib import Path
from config.settings import get_path_settings

logger = logging.getLogger(__name__)


class BackupService:

    def __init__(self):
        try:
            path_settings = get_path_settings()
            self.db_path = Path(path_settings.data_dir) / "asycuda.db"
        except Exception as e:
            logger.debug(f"PathSettings nedostupan, koristim default putanju: {e}")
            self.db_path = Path.home() / ".deklarant_pro" / "asycuda.db"

    def get_database_size(self) -> int:
        try:
            if self.db_path.exists():
                return self.db_path.stat().st_size
            return 0
        except Exception:
            return 0
