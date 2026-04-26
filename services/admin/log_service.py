import logging
logger = logging.getLogger(__name__)
"""
Log Service - Log reading and filtering.

TASK 12: Implementirano sa statistikom, export-om, boljim parsing-om
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import re
import csv


class LogService:
    """
    Service za čitanje i filtriranje logova.
    
    TASK 12: Čitanje logova sa statistikom, export-om i boljim parsing-om
    """

    # Regex pattern za parse-ovanje log linija
    # Format: "2024-01-01 12:00:00 - INFO - Message"
    LOG_PATTERN = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*-\s*(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*-\s*(.+)$',
        re.IGNORECASE
    )

    def __init__(self):
        """Inicijalizacija."""
        self.log_dir = Path.home() / ".deklarant_pro" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.log_dir / "asycuda.log"

    def get_recent_logs(self, count: int = 100) -> List[Dict[str, Any]]:
        """
        Vrati nedavne log-ove.

        Args:
            count: Broj log-ova za vratiti

        Returns:
            Lista dict-ova sa log entries
        """
        if not self.log_file.exists():
            return []

        try:
            logs = []
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Get last 'count' lines
            for line in lines[-count:]:
                line = line.strip()
                if line:
                    parsed = self._parse_log_line(line)
                    if parsed:
                        logs.append(parsed)

            return logs

        except Exception as e:
            logger.error(f"❌ Error reading logs: {e}")
            return []

    def get_all_logs(self) -> List[Dict[str, Any]]:
        """
        Vrati sve log-ove iz fajla.

        Returns:
            Lista dict-ova sa log entries
        """
        if not self.log_file.exists():
            return []

        try:
            logs = []
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        parsed = self._parse_log_line(line)
                        if parsed:
                            logs.append(parsed)

            return logs

        except Exception as e:
            logger.error(f"❌ Error reading all logs: {e}")
            return []

    def filter_logs(
        self,
        level: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Filtriraj log-ove.

        Args:
            level: Log level (INFO, DEBUG, WARNING, ERROR)
            search: Search term
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            Lista filtriranih log entries
        """
        logs = self.get_all_logs()  # Get all for filtering
        filtered = []

        for log in logs:
            # Filter by level
            if level and log.get('level') != level:
                continue

            # Filter by search term
            if search and search.lower() not in log.get('message', '').lower():
                continue

            # Filter by date range
            log_date = log.get('timestamp', '')[:10]  # Extract YYYY-MM-DD
            if start_date and log_date < start_date:
                continue
            if end_date and log_date > end_date:
                continue

            filtered.append(log)

        return filtered

    def get_log_statistics(self) -> Dict[str, Any]:
        """
        Vrati statistiku logova.

        Returns:
            Dict sa statistikama
        """
        logs = self.get_all_logs()
        
        total = len(logs)
        by_level = {
            'DEBUG': 0,
            'INFO': 0,
            'WARNING': 0,
            'ERROR': 0,
            'CRITICAL': 0,
            'UNKNOWN': 0,
        }
        
        for log in logs:
            level = log.get('level', 'UNKNOWN')
            if level in by_level:
                by_level[level] += 1
            else:
                by_level['UNKNOWN'] += 1

        # Get date range
        dates = [log.get('timestamp', '')[:10] for log in logs if log.get('timestamp')]
        oldest = min(dates) if dates else None
        newest = max(dates) if dates else None

        return {
            'total': total,
            'by_level': by_level,
            'oldest_log': oldest,
            'newest_log': newest,
            'file_size': self.log_file.stat().st_size if self.log_file.exists() else 0,
        }

    def export_logs(
        self,
        output_path: str,
        format: str = 'txt',
        filtered_logs: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Eksportuj log-ove u fajl.

        Args:
            output_path: Put do izlaznog fajla
            format: Format ('txt' ili 'csv')
            filtered_logs: Lista logova za eksport (ako None, koristi sve)

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            logs = filtered_logs if filtered_logs is not None else self.get_all_logs()
            
            if not logs:
                logger.warning("⚠️  Nema logova za eksport")
                return False

            output_file = Path(output_path)

            if format.lower() == 'csv':
                return self._export_to_csv(output_file, logs)
            else:
                return self._export_to_txt(output_file, logs)

        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            return False

    def _export_to_txt(self, output_file: Path, logs: List[Dict[str, Any]]) -> bool:
        """
        Eksportuj log-ove u TXT format.

        Args:
            output_file: Put do izlaznog fajla
            logs: Lista logova

        Returns:
            True ako uspješno
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("ASYCUDA PRO - LOG EXPORT\n")
            f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total logs: {len(logs)}\n")
            f.write("=" * 80 + "\n\n")

            for log in logs:
                timestamp = log.get('timestamp', '')
                level = log.get('level', '')
                message = log.get('message', '')
                f.write(f"[{timestamp}] {level}: {message}\n")

            f.write("\n" + "=" * 80 + "\n")
            f.write("END OF LOG\n")
            f.write("=" * 80 + "\n")

        logger.info(f"✅ TXT export completed: {output_file}")
        return True

    def _export_to_csv(self, output_file: Path, logs: List[Dict[str, Any]]) -> bool:
        """
        Eksportuj log-ove u CSV format.

        Args:
            output_file: Put do izlaznog fajla
            logs: Lista logova

        Returns:
            True ako uspješno
        """
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow(['Timestamp', 'Level', 'Message'])
            
            # Data
            for log in logs:
                writer.writerow([
                    log.get('timestamp', ''),
                    log.get('level', ''),
                    log.get('message', '')
                ])

        logger.info(f"✅ CSV export completed: {output_file}")
        return True

    def clear_logs(self, keep_last: int = 0) -> bool:
        """
        Obriši log-ove.

        Args:
            keep_last: Broj zadnjih linija za zadržati (0 = obriši sve)

        Returns:
            True ako uspješno, False ako ne
        """
        try:
            if not self.log_file.exists():
                return True

            if keep_last == 0:
                # Obriši sve
                self.log_file.unlink()
                logger.info("✅ Svi logovi obrisani")
                return True
            else:
                # Zadrži zadnjih N linija
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                if len(lines) > keep_last:
                    with open(self.log_file, 'w', encoding='utf-8') as f:
                        f.writelines(lines[-keep_last:])
                    logger.info(f"✅ Zadržano zadnjih {keep_last} linija")

                return True

        except Exception as e:
            logger.error(f"❌ Clear failed: {e}")
            return False

    def get_available_log_files(self) -> List[Dict[str, Any]]:
        """
        Vrati listu dostupnih log fajlova.

        Returns:
            Lista dict-ova sa informacijama o fajlovima
        """
        log_files = []

        if not self.log_dir.exists():
            return log_files

        for filepath in self.log_dir.glob("*.log"):
            stat = filepath.stat()
            log_files.append({
                'filename': filepath.name,
                'filepath': str(filepath),
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'is_current': filepath == self.log_file,
            })

        # Sort by modified date (newest first)
        log_files.sort(key=lambda x: x['modified'], reverse=True)
        return log_files

    def switch_log_file(self, filename: str) -> bool:
        """
        Promijeni aktivni log fajl.

        Args:
            filename: Ime fajla za switch-ovanje

        Returns:
            True ako uspješno, False ako ne
        """
        new_log_file = self.log_dir / filename

        if not new_log_file.exists():
            logger.error(f"❌ Log file not found: {filename}")
            return False

        self.log_file = new_log_file
        logger.info(f"✅ Switched to log file: {filename}")
        return True

    def _parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parsiraj jednu log liniju koristeći regex.

        Args:
            line: Log linija

        Returns:
            Dict sa parsed informacijama ili None
        """
        # Probaj sa regex-om
        match = self.LOG_PATTERN.match(line)
        if match:
            return {
                'timestamp': match.group(1),
                'level': match.group(2).upper(),
                'message': match.group(3),
            }

        # Fallback: probaj jednostavniji format
        try:
            parts = line.split(' - ', 2)
            if len(parts) >= 3:
                return {
                    'timestamp': parts[0].strip(),
                    'level': parts[1].strip().upper(),
                    'message': parts[2].strip(),
                }
        except Exception:
            pass

        # Ako ništa ne radi, vrati cijelu liniju kao message
        return {
            'timestamp': '',
            'level': 'UNKNOWN',
            'message': line,
        }

    def write_log(self, level: str, message: str) -> bool:
        """
        Zapiši jedan log (za testiranje).

        Args:
            level: Log level (INFO, DEBUG, WARNING, ERROR)
            message: Poruka

        Returns:
            True ako uspješno
        """
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_line = f"{timestamp} - {level} - {message}\n"

            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)

            return True
        except Exception as e:
            logger.error(f"❌ Write log failed: {e}")
            return False
