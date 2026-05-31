import logging
logger = logging.getLogger(__name__)
"""
Backup Service - Backup/Restore operations.

TASK 10: Implementirano sa validacijom, backup prije restore-a, cleanup-om
"""

from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import shutil
import sqlite3
from datetime import datetime
from config.settings import get_db_settings, get_path_settings


class BackupService:
    """
    Service za backup/restore operacije.
    
    TASK 10: Backup/Restore sa validacijom, cleanup-om i progress callback-om
    """

    # Koliko backup-a zadržati
    MAX_BACKUPS = 10

    def __init__(self):
        """Inicijalizacija."""
        self.backup_dir = Path.home() / ".deklarant_pro" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Putanja do database - koristi PathSettings
        try:
            path_settings = get_path_settings()
            self.db_path = Path(path_settings.data_dir) / "asycuda.db"
        except Exception as e:
            logger.debug(f"PathSettings nedostupan, koristim default putanju: {e}")
            self.db_path = Path.home() / ".deklarant_pro" / "asycuda.db"

    def create_backup(self, backup_path: str = None, 
                      progress_callback: Optional[Callable[[int], None]] = None) -> bool:
        """
        Kreiraj database backup.

        Args:
            backup_path: Put gdje sačuvati backup (opciono)
            progress_callback: Callback za progress (0-100)

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            if progress_callback:
                progress_callback(0)

            # 1. Validacija: database mora postojati
            if not self.db_path.exists():
                logger.error(f"❌ Database not found: {self.db_path}")
                if progress_callback:
                    progress_callback(0)
                return False

            # 2. Validacija: database mora biti validan SQLite fajl
            if not self._validate_database(self.db_path):
                logger.error(f"❌ Database validation failed: {self.db_path}")
                if progress_callback:
                    progress_callback(0)
                return False

            if progress_callback:
                progress_callback(20)

            # 3. Odredi putanju
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.backup_dir / f"asycuda_backup_{timestamp}.db"
            else:
                backup_path = Path(backup_path)

            # 4. Kopiraj database
            shutil.copy2(self.db_path, backup_path)
            
            if progress_callback:
                progress_callback(80)

            # 5. Validiraj backup
            if not self._validate_database(backup_path):
                logger.error(f"❌ Backup validation failed: {backup_path}")
                backup_path.unlink(missing_ok=True)
                if progress_callback:
                    progress_callback(0)
                return False

            if progress_callback:
                progress_callback(100)

            logger.info(f"✅ Backup created: {backup_path}")
            
            # 6. Cleanup starih backup-a
            self._cleanup_old_backups()
            
            return True

        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            if progress_callback:
                progress_callback(0)
            return False

    def restore_backup(self, backup_path: str,
                       create_backup_before: bool = True,
                       progress_callback: Optional[Callable[[int], None]] = None) -> bool:
        """
        Restore database iz backup-a.

        Args:
            backup_path: Put do backup fajla
            create_backup_before: Kreiraj backup trenutne baze prije restore-a
            progress_callback: Callback za progress (0-100)

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            if progress_callback:
                progress_callback(0)

            backup_file = Path(backup_path)

            # 1. Validacija: backup fajl mora postojati
            if not backup_file.exists():
                logger.error(f"❌ Backup file not found: {backup_path}")
                if progress_callback:
                    progress_callback(0)
                return False

            # 2. Validacija: backup mora biti validan SQLite
            if not self._validate_database(backup_file):
                logger.error(f"❌ Backup validation failed: {backup_path}")
                if progress_callback:
                    progress_callback(0)
                return False

            if progress_callback:
                progress_callback(20)

            # 3. Kreiraj backup trenutne baze (opciono ali preporučeno)
            if create_backup_before and self.db_path.exists():
                logger.debug("📦 Kreiranje backup-a trenutne baze prije restore-a...")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                auto_backup_path = self.backup_dir / f"auto_backup_before_restore_{timestamp}.db"
                shutil.copy2(self.db_path, auto_backup_path)
                logger.info(f"   ✅ Auto backup kreiran: {auto_backup_path}")
                
                if progress_callback:
                    progress_callback(40)

            # 4. Restore-uj backup
            shutil.copy2(backup_file, self.db_path)
            
            if progress_callback:
                progress_callback(80)

            # 5. Validiraj restore-ovanu bazu
            if not self._validate_database(self.db_path):
                logger.error(f"❌ Restore validation failed!")
                # Pokušaj rollback na auto backup
                if create_backup_before and auto_backup_path.exists():
                    logger.debug("🔄 Pokušaj rollback-a...")
                    shutil.copy2(auto_backup_path, self.db_path)
                
                if progress_callback:
                    progress_callback(0)
                return False

            if progress_callback:
                progress_callback(100)

            logger.info(f"✅ Database restored from: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            if progress_callback:
                progress_callback(0)
            return False

    def get_available_backups(self) -> List[Dict[str, Any]]:
        """
        Vrati listu dostupnih backup-a.

        Returns:
            Lista dict-ova sa backup info-m
        """
        backups = []

        if not self.backup_dir.exists():
            return backups

        for filepath in self.backup_dir.glob("*.db"):
            # Preskoči auto backup-ove ako nisu traženi
            if filepath.name.startswith('auto_backup_'):
                continue
                
            stat = filepath.stat()
            backups.append({
                'filename': filepath.name,
                'filepath': str(filepath),
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'is_auto_backup': False,
            })

        # Sort by date (newest first)
        backups.sort(key=lambda x: x['created'], reverse=True)
        return backups

    def get_database_size(self) -> int:
        """
        Vrati veličinu database fajla.

        Returns:
            Veličina u bajtovima
        """
        try:
            if self.db_path.exists():
                return self.db_path.stat().st_size
            return 0
        except Exception:
            return 0

    def get_backup_stats(self) -> Dict[str, Any]:
        """
        Vrati statistiku backup-a.

        Returns:
            Dict sa statistikama
        """
        backups = self.get_available_backups()
        
        total_size = sum(b['size'] for b in backups)
        
        return {
            'total_backups': len(backups),
            'total_size': total_size,
            'oldest_backup': backups[-1]['created'] if backups else None,
            'newest_backup': backups[0]['created'] if backups else None,
        }

    def delete_backup(self, backup_path: str) -> bool:
        """
        Obriši specifični backup.

        Args:
            backup_path: Put do backup fajla

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            backup_file = Path(backup_path)
            
            if not backup_file.exists():
                logger.error(f"❌ Backup file not found: {backup_path}")
                return False
            
            backup_file.unlink()
            logger.info(f"✅ Backup obrisan: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Delete failed: {e}")
            return False

    def _validate_database(self, db_path: Path) -> bool:
        """
        Validiraj SQLite database fajl.

        Args:
            db_path: Put do database fajla

        Returns:
            True ako je validan, False ako nije
        """
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Probaj izvršiti jednostavan query
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
            conn.close()
            
            return result is not None and result[0] == 1
        except Exception as e:
            logger.debug(f"Database validation error: {e}")
            return False

    def _cleanup_old_backups(self, keep_count: int = None):
        """
        Obriši stare backup-e, zadrži samo zadnjih N.

        Args:
            keep_count: Broj backup-a za zadržati (default: MAX_BACKUPS)
        """
        try:
            if keep_count is None:
                keep_count = self.MAX_BACKUPS

            backups = self.get_available_backups()
            
            if len(backups) > keep_count:
                # Obriši najstarije
                for backup in backups[keep_count:]:
                    backup_file = Path(backup['filepath'])
                    backup_file.unlink()
                    logger.debug(f"🗑️  Obrisan stari backup: {backup['filename']}")
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")

    def get_auto_backups(self) -> List[Dict[str, Any]]:
        """
        Vrati listu auto backup-a (kreiranih prije restore-a).

        Returns:
            Lista dict-ova sa auto backup info-m
        """
        auto_backups = []

        if not self.backup_dir.exists():
            return auto_backups

        for filepath in self.backup_dir.glob("auto_backup_*.db"):
            stat = filepath.stat()
            auto_backups.append({
                'filename': filepath.name,
                'filepath': str(filepath),
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'is_auto_backup': True,
            })

        auto_backups.sort(key=lambda x: x['created'], reverse=True)
        return auto_backups
