"""
Backup Service — SQLite i PostgreSQL backup/restore.

Podržava:
- SQLite: file-copy bekap svih lokalnih .db fajlova (deklarant_sistem, zvanicna_tarifa, itd.)
- PostgreSQL: pg_dump bekap centralne baze na dmserver-u
"""

import logging
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from config.settings import get_path_settings

logger = logging.getLogger(__name__)

BACKUP_DIR = Path.home() / ".deklarant_pro" / "backups"
MAX_BACKUPS = 20


class BackupService:

    def __init__(self):
        try:
            path_settings = get_path_settings()
            self.db_path = Path(path_settings.data_dir) / "asycuda.db"
        except Exception as e:
            logger.debug(f"PathSettings nedostupan, koristim default putanju: {e}")
            self.db_path = Path.home() / ".deklarant_pro" / "asycuda.db"
        self.backup_dir = BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    # ── SQLite ──────────────────────────────────────────────────

    def get_database_size(self) -> int:
        try:
            if self.db_path.exists():
                return self.db_path.stat().st_size
            return 0
        except Exception:
            return 0

    def create_backup(self, db_path: str = "", label: str = "") -> Optional[Path]:
        """
        Bekap pojedinačne SQLite baze.

        Args:
            db_path: Putanja do .db fajla (default: asycuda.db iz PathSettings)
            label: Opis za naziv fajla (opciono)

        Returns:
            Path do kreiranog bekapa ili None
        """
        src = Path(db_path) if db_path else self.db_path
        if not src.exists():
            logger.error(f"Baza ne postoji: {src}")
            return None
        if not self._validate_sqlite(src):
            logger.error(f"Nevalidna SQLite baza: {src}")
            return None

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = src.stem
        label_part = f"_{label}" if label else ""
        dest = self.backup_dir / f"{name}{label_part}_{ts}.db"

        shutil.copy2(src, dest)
        if not self._validate_sqlite(dest):
            logger.error(f"Bekap validacija neuspješna: {dest}")
            dest.unlink(missing_ok=True)
            return None

        logger.info(f"SQLite bekap: {src.name} → {dest.name} ({dest.stat().st_size:,} B)")
        self._cleanup_old_backups()
        return dest

    def create_full_backup(self) -> Dict[str, Optional[Path]]:
        """
        Bekap SVIH SQLite baza u database/ folderu + asycuda.db.

        Returns:
            Dict {ime_baze: Path do bekapa ili None}
        """
        results: Dict[str, Optional[Path]] = {}

        db_dir = Path("database")
        if db_dir.exists():
            for f in sorted(db_dir.glob("*.db")):
                dest = self.create_backup(str(f))
                results[f.stem] = dest

        if self.db_path.exists():
            dest = self.create_backup(str(self.db_path), label="runtime")
            results[self.db_path.stem] = dest

        return results

    def restore_backup(self, backup_path: str, target_path: str = "",
                       create_backup_before: bool = True) -> bool:
        """
        Restore SQLite baze iz bekapa.

        Args:
            backup_path: Put do .db bekapa
            target_path: Putanja gdje restore-ovati (default: originalna lokacija)
            create_backup_before: Kreiraj bekap trenutne baze prije restore-a

        Returns:
            True ako uspješno
        """
        backup_file = Path(backup_path)
        if not backup_file.exists():
            logger.error(f"Bekap fajl ne postoji: {backup_path}")
            return False
        if not self._validate_sqlite(backup_file):
            logger.error(f"Nevalidan bekap: {backup_path}")
            return False

        target = Path(target_path) if target_path else self.db_path

        if create_backup_before and target.exists():
            logger.info("Pravim bekap trenutne baze prije restore-a...")
            self.create_backup(str(target), label="pre_restore")

        shutil.copy2(backup_file, target)
        if not self._validate_sqlite(target):
            logger.error(f"Restore validacija neuspješna: {target}")
            return False

        logger.info(f"SQLite restore: {backup_file.name} → {target}")
        return True

    def list_backups(self) -> List[Dict[str, Any]]:
        """Vrati listu svih dostupnih bekapa."""
        backups = []
        if not self.backup_dir.exists():
            return backups
        for f in sorted(self.backup_dir.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.suffix in (".db", ".dump"):
                st = f.stat()
                backups.append({
                    "filename": f.name,
                    "filepath": str(f),
                    "size": st.st_size,
                    "size_mb": round(st.st_size / (1024 * 1024), 2),
                    "created": datetime.fromtimestamp(st.st_mtime).isoformat(),
                    "type": "sqlite" if f.suffix == ".db" else "postgresql",
                })
        return backups

    def delete_backup(self, backup_path: str) -> bool:
        p = Path(backup_path)
        if not p.exists():
            return False
        p.unlink()
        logger.info(f"Obrisan bekap: {p.name}")
        return True

    # ── PostgreSQL ──────────────────────────────────────────────

    def create_pg_backup(self, label: str = "") -> Optional[Path]:
        """
        Bekap PostgreSQL baze koristeći pg_dump.

        Zahtijeva pg_dump u PATH-u i ispravan .env sa DB_* varijablama.

        Args:
            label: Opis za naziv fajla (opciono)

        Returns:
            Path do .dump fajla ili None
        """
        try:
            from config.settings import get_db_settings
            db = get_db_settings()
        except Exception as e:
            logger.error(f"Ne mogu da pročitam DB podešavanja: {e}")
            return None

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        label_part = f"_{label}" if label else ""
        dest = self.backup_dir / f"pg_{db.database}{label_part}_{ts}.dump"

        env = os.environ.copy()
        env["PGPASSWORD"] = db.password

        cmd = [
            "pg_dump",
            "-h", db.host,
            "-p", str(db.port),
            "-U", db.user,
            "-d", db.database,
            "-F", "c",
            "-f", str(dest),
        ]

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                logger.error(f"pg_dump greška: {stderr}")
                dest.unlink(missing_ok=True)
                return None

            if not dest.exists() or dest.stat().st_size == 0:
                logger.error("pg_dump kreirao prazan fajl")
                dest.unlink(missing_ok=True)
                return None

            logger.info(
                f"PostgreSQL bekap: {db.database}@{db.host} → "
                f"{dest.name} ({dest.stat().st_size:,} B)"
            )
            self._cleanup_old_backups()
            return dest

        except FileNotFoundError:
            logger.error(
                "pg_dump nije pronađen u PATH-u. Instaliraj PostgreSQL client tools "
                "ili dodaj putanju do pg_dump.exe u PATH."
            )
            return None
        except subprocess.TimeoutExpired:
            logger.error("pg_dump je prekoračio vremensko ograničenje (5 min)")
            dest.unlink(missing_ok=True)
            return None
        except Exception as e:
            logger.error(f"PostgreSQL bekap greška: {e}")
            dest.unlink(missing_ok=True)
            return None

    def restore_pg_backup(self, backup_path: str, create_backup_before: bool = True) -> bool:
        """
        Restore PostgreSQL baze iz .dump bekapa koristeći pg_restore.

        Args:
            backup_path: Put do .dump fajla
            create_backup_before: Kreiraj bekap trenutne baze prije restore-a

        Returns:
            True ako uspješno
        """
        backup_file = Path(backup_path)
        if not backup_file.exists():
            logger.error(f"Bekap fajl ne postoji: {backup_path}")
            return False

        try:
            from config.settings import get_db_settings
            db = get_db_settings()
        except Exception as e:
            logger.error(f"Ne mogu da pročitam DB podešavanja: {e}")
            return False

        if create_backup_before:
            logger.info("Pravim bekap trenutne PostgreSQL baze prije restore-a...")
            self.create_pg_backup(label="pre_restore")

        env = os.environ.copy()
        env["PGPASSWORD"] = db.password

        cmd = [
            "pg_restore",
            "-h", db.host,
            "-p", str(db.port),
            "-U", db.user,
            "-d", db.database,
            "--clean",
            "--if-exists",
            str(backup_file),
        ]

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                logger.error(f"pg_restore greška: {result.stderr.strip()}")
                return False

            logger.info(f"PostgreSQL restore: {backup_file.name} → {db.database}@{db.host}")
            return True

        except FileNotFoundError:
            logger.error("pg_restore nije pronađen u PATH-u.")
            return False
        except subprocess.TimeoutExpired:
            logger.error("pg_restore je prekoračio vremensko ograničenje (10 min)")
            return False
        except Exception as e:
            logger.error(f"PostgreSQL restore greška: {e}")
            return False

    # ── Interno ─────────────────────────────────────────────────

    @staticmethod
    def _validate_sqlite(db_path: Path) -> bool:
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("SELECT 1")
            conn.close()
            return True
        except Exception:
            return False

    def _cleanup_old_backups(self, keep_count: int = MAX_BACKUPS) -> None:
        try:
            backups = self.list_backups()
            if len(backups) > keep_count:
                for b in backups[keep_count:]:
                    Path(b["filepath"]).unlink(missing_ok=True)
                    logger.debug(f"Obrisan stari bekap: {b['filename']}")
        except Exception as e:
            logger.warning(f"Cleanup starih bekapa nije uspio: {e}")
