"""
Analytics Service - Statistics gathering.

TASK 16: Implementirano sa detaljnom statistikom, trendovima, mock podacima
"""

import logging
logger = logging.getLogger(__name__)

from typing import Dict, Any
from pathlib import Path
import sqlite3
from config.settings import get_path_settings


class AnalyticsService:
    """
    Service za prikupljanje statistika.
    
    TASK 16: Detaljna statistika sa mock podacima i trendovima
    """

    def __init__(self):
        """Inicijalizacija."""
        try:
            path_settings = get_path_settings()
            self.db_path = Path(path_settings.data_dir) / "asycuda.db"
        except Exception as e:
            logger.debug(f"PathSettings nedostupan, koristim default putanju: {e}")
            self.db_path = Path.home() / ".deklarant_pro" / "asycuda.db"
        
        # Mock podaci za demonstraciju (dok se ne doda import_log tabela)
        self.mock_data = self._generate_mock_data()

    def _generate_mock_data(self) -> Dict[str, Any]:
        """
        Generiši mock podatke za demonstraciju.

        Returns:
            Dict sa mock podacima
        """
        return {
            'total_imports': 1250,
            'imports_today': 15,
            'imports_this_week': 85,
            'imports_this_month': 320,
            'imports_last_month': 285,
            'parser_usage': [
                {'name': 'Maxi Parser', 'count': 450, 'percentage': 36.0},
                {'name': 'Metro Parser', 'count': 320, 'percentage': 25.6},
                {'name': 'Delta Parser', 'count': 180, 'percentage': 14.4},
                {'name': 'Univerzal Parser', 'count': 150, 'percentage': 12.0},
                {'name': 'Ostali', 'count': 150, 'percentage': 12.0},
            ],
        }

    def get_import_statistics(self) -> Dict[str, Any]:
        """
        Vrati detaljnu import statistiku.

        Returns:
            Dict sa statistikama
        """
        stats = {
            'total_imports': 0,
            'imports_today': 0,
            'imports_this_week': 0,
            'imports_this_month': 0,
            'imports_last_month': 0,
            'trend': 0.0,  # Procenat rasta/pada
            'trend_direction': 'stable',  # 'up', 'down', 'stable'
            'by_parser': {},
            'daily_average': 0.0,
        }

        # Prvo probaj iz baze
        try:
            if self.db_path.exists():
                stats = self._get_import_stats_from_db(stats)
        except Exception as e:
            logger.warning(f"⚠️  Database error: {e}")

        # Ako nema podataka iz baze, koristi mock
        if stats['total_imports'] == 0:
            mock = self.mock_data
            stats.update({
                'total_imports': mock['total_imports'],
                'imports_today': mock['imports_today'],
                'imports_this_week': mock['imports_this_week'],
                'imports_this_month': mock['imports_this_month'],
                'imports_last_month': mock['imports_last_month'],
            })
            
            # Izračunaj trend
            if mock['imports_last_month'] > 0:
                change = mock['imports_this_month'] - mock['imports_last_month']
                stats['trend'] = round((change / mock['imports_last_month']) * 100, 1)
                
                if stats['trend'] > 5:
                    stats['trend_direction'] = 'up'
                elif stats['trend'] < -5:
                    stats['trend_direction'] = 'down'
                else:
                    stats['trend_direction'] = 'stable'
            
            # Daily average
            stats['daily_average'] = round(mock['imports_this_month'] / 30, 1)
            
            # By parser
            stats['by_parser'] = {p['name']: p['count'] for p in mock['parser_usage']}

        return stats

    def _get_import_stats_from_db(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pokušaj dohvatiti statistiku iz baze.

        Args:
            stats: Postojeći stats dict

        Returns:
            Ažurirani stats dict
        """
        if not self.db_path.exists():
            return stats

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # Total imports
            cursor.execute("SELECT COUNT(*) FROM deklaracije")
            result = cursor.fetchone()
            if result:
                stats['total_imports'] = result[0]
        except Exception as e:
            logger.debug(f"Tabela 'deklaracije' nedostupna: {e}")

        conn.close()
        return stats

