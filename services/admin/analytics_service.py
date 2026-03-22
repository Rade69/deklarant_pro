import logging
logger = logging.getLogger(__name__)
"""
Analytics Service - Statistics gathering.

TASK 16: Implementirano sa detaljnom statistikom, trendovima, mock podacima
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import sqlite3
import json
from datetime import datetime, timedelta
from config.settings import get_db_settings, get_path_settings


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
        except:
            self.db_path = Path.home() / ".asycuda_pro" / "asycuda.db"
        
        # Mock podaci za demonstraciju (dok se ne doda import_log tabela)
        self.mock_data = self._generate_mock_data()

    def _generate_mock_data(self) -> Dict[str, Any]:
        """
        Generiši mock podatke za demonstraciju.

        Returns:
            Dict sa mock podacima
        """
        now = datetime.now()
        
        return {
            'total_imports': 1250,
            'imports_today': 15,
            'imports_this_week': 85,
            'imports_this_month': 320,
            'imports_last_month': 285,
            'total_declarations': 890,
            'declarations_today': 8,
            'declarations_this_week': 52,
            'declarations_this_month': 210,
            'by_status': {
                'COMPLETED': 650,
                'PENDING': 120,
                'ERROR': 45,
                'DRAFT': 75
            },
            'parser_usage': [
                {'name': 'Maxi Parser', 'count': 450, 'percentage': 36.0},
                {'name': 'Metro Parser', 'count': 320, 'percentage': 25.6},
                {'name': 'Delta Parser', 'count': 180, 'percentage': 14.4},
                {'name': 'Univerzal Parser', 'count': 150, 'percentage': 12.0},
                {'name': 'Ostali', 'count': 150, 'percentage': 12.0},
            ],
            'daily_imports': [
                {'date': (now - timedelta(days=i)).strftime('%Y-%m-%d'), 'count': 10 + i * 2}
                for i in range(30)
            ],
            'monthly_trend': [
                {'month': f'{2025}-{m:02d}', 'imports': 200 + m * 20, 'declarations': 150 + m * 15}
                for m in range(1, 13)
            ]
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
        except Exception:
            pass

        conn.close()
        return stats

    def get_parser_usage(self) -> List[Dict[str, Any]]:
        """
        Vrati parser usage statistiku.

        Returns:
            Lista dict-ova sa parser usage-om
        """
        # Prvo probaj iz baze
        try:
            if self.db_path.exists():
                usage = self._get_parser_usage_from_db()
                if usage:
                    return usage
        except Exception as e:
            logger.warning(f"⚠️  Database error: {e}")

        # Vrati mock podatke
        return self.mock_data['parser_usage']

    def _get_parser_usage_from_db(self) -> List[Dict[str, Any]]:
        """
        Pokušaj dohvatiti parser usage iz baze.

        Returns:
            Lista dict-ova sa parser usage-om
        """
        usage = []

        if not self.db_path.exists():
            return usage

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # Ako postoji import_log tabela
            cursor.execute("""
                SELECT parser_name, COUNT(*) as count
                FROM import_log
                GROUP BY parser_name
                ORDER BY count DESC
                LIMIT 5
            """)
            
            results = cursor.fetchall()
            total = sum(row[1] for row in results)
            
            for row in results:
                usage.append({
                    'name': row[0],
                    'count': row[1],
                    'percentage': round((row[1] / total) * 100, 1) if total > 0 else 0
                })
        except Exception:
            # Tabela ne postoji, vrati praznu listu
            pass

        conn.close()
        return usage

    def get_declaration_statistics(self) -> Dict[str, Any]:
        """
        Vrati detaljnu statistiku deklaracija.

        Returns:
            Dict sa statistikama
        """
        stats = {
            'total': 0,
            'this_month': 0,
            'last_month': 0,
            'trend': 0.0,
            'trend_direction': 'stable',
            'by_status': {},
            'completion_rate': 0.0,
        }

        # Prvo probaj iz baze
        try:
            if self.db_path.exists():
                stats = self._get_declaration_stats_from_db(stats)
        except Exception as e:
            logger.warning(f"⚠️  Database error: {e}")

        # Ako nema podataka iz baze, koristi mock
        if stats['total'] == 0:
            mock = self.mock_data
            stats.update({
                'total': mock['total_declarations'],
                'this_month': mock['declarations_this_month'],
                'last_month': mock['declarations_this_month'] * 0.9,  # Mock
                'by_status': mock['by_status'],
            })
            
            # Trend
            if stats['last_month'] > 0:
                change = stats['this_month'] - stats['last_month']
                stats['trend'] = round((change / stats['last_month']) * 100, 1)
                
                if stats['trend'] > 5:
                    stats['trend_direction'] = 'up'
                elif stats['trend'] < -5:
                    stats['trend_direction'] = 'down'
                else:
                    stats['trend_direction'] = 'stable'
            
            # Completion rate
            if stats['total'] > 0:
                completed = stats['by_status'].get('COMPLETED', 0)
                stats['completion_rate'] = round((completed / stats['total']) * 100, 1)

        return stats

    def _get_declaration_stats_from_db(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pokušaj dohvatiti statistiku deklaracija iz baze.

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
            # Total declarations
            cursor.execute("SELECT COUNT(*) FROM deklaracije")
            result = cursor.fetchone()
            if result:
                stats['total'] = result[0]

            # By status
            cursor.execute("""
                SELECT status, COUNT(*)
                FROM deklaracije
                GROUP BY status
            """)
            stats['by_status'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Completion rate
            if stats['total'] > 0:
                completed = stats['by_status'].get('COMPLETED', 0)
                stats['completion_rate'] = round((completed / stats['total']) * 100, 1)
                
        except Exception as e:
            logger.warning(f"⚠️  Error: {e}")

        conn.close()
        return stats

    def get_daily_statistics(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Vrati dnevnu statistiku za zadnjih N dana.

        Args:
            days: Broj dana

        Returns:
            Lista dict-ova sa dnevnim statistikama
        """
        # Vrati mock podatke za sada
        return self.mock_data['daily_imports'][-days:]

    def get_monthly_trend(self) -> List[Dict[str, Any]]:
        """
        Vrati mjesečni trend za zadnjih 12 mjeseci.

        Returns:
            Lista dict-ova sa mjesečnim trendom
        """
        # Vrati mock podatke za sada
        return self.mock_data['monthly_trend']

    def get_summary(self) -> Dict[str, Any]:
        """
        Vrati sažetak svih statistika.

        Returns:
            Dict sa sažetkom
        """
        import_stats = self.get_import_statistics()
        declaration_stats = self.get_declaration_statistics()
        parser_usage = self.get_parser_usage()

        return {
            'imports': import_stats,
            'declarations': declaration_stats,
            'parser_usage': parser_usage,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    def export_statistics(self, output_path: str, format: str = 'json') -> bool:
        """
        Eksportuj statistiku u fajl.

        Args:
            output_path: Put do izlaznog fajla
            format: Format ('json' ili 'csv')

        Returns:
            True ako uspješno
        """
        try:
            summary = self.get_summary()
            
            if format.lower() == 'json':
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, indent=2, ensure_ascii=False)
            else:
                # CSV export (simplified)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write("Category,Metric,Value\n")
                    f.write(f"Imports,Total,{summary['imports']['total_imports']}\n")
                    f.write(f"Imports,Today,{summary['imports']['imports_today']}\n")
                    f.write(f"Imports,This Week,{summary['imports']['imports_this_week']}\n")
                    f.write(f"Imports,This Month,{summary['imports']['imports_this_month']}\n")
                    f.write(f"Declarations,Total,{summary['declarations']['total']}\n")
                    f.write(f"Declarations,Completion Rate,{summary['declarations']['completion_rate']}%\n")

            logger.info(f"✅ Statistics exported: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            return False
