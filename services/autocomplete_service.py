# services/autocomplete_service.py
"""
Optimized autocomplete za trgovačke nazive
"""

from functools import lru_cache
import time
from typing import List, Optional


class AutocompleteService:
    """Smart autocomplete sa performance optimizacijama"""

    def __init__(self, db_service):
        self.db = db_service
        self._last_query_time = 0
        self._min_query_interval = 0.3  # Debouncing - 300ms

    def search_nazivi(
        self, query: str, tarifni_broj: Optional[str] = None, limit: int = 10
    ) -> List[str]:
        """
        Autocomplete search sa optimizacijama

        Optimizacije:
        1. Min length check (barem 3 karaktera)
        2. Debouncing (ne query-uj prebrzo)
        3. DB index usage
        4. LIMIT clause
        5. Prepared statements (caching)
        """

        # 1. Min length check
        if len(query) < 3:
            return []

        # 2. Debouncing
        current_time = time.time()
        if current_time - self._last_query_time < self._min_query_interval:
            return []  # Ignoriši prebrze query-je

        self._last_query_time = current_time

        # 3. DB query sa optimizacijama
        if tarifni_broj:
            # Search within specific tariff
            sql = """
                SELECT DISTINCT trgovacki_naziv
                FROM tarifa_nazivi
                WHERE tarifni_broj = %s
                  AND trgovacki_naziv ILIKE %s
                ORDER BY frequency DESC
                LIMIT %s
            """
            params = (tarifni_broj, f"%{query}%", limit)
        else:
            # Global search
            sql = """
                SELECT DISTINCT trgovacki_naziv
                FROM tarifa_nazivi
                WHERE trgovacki_naziv ILIKE %s
                ORDER BY frequency DESC
                LIMIT %s
            """
            params = (f"%{query}%", limit)

        # Execute with prepared statement (cached)
        return self.db.fetch_all(sql, params)

    @lru_cache(maxsize=100)
    def get_frequent_nazivi_for_tariff(
        self, tarifni_broj: str, limit: int = 10
    ) -> List[str]:
        """
        Cache najčešćih naziva za tarifu
        LRU cache - 100 različitih tarifa u memoriji
        """

        sql = """
            SELECT trgovacki_naziv
            FROM tarifa_nazivi
            WHERE tarifni_broj = %s
            ORDER BY frequency DESC
            LIMIT %s
        """

        return self.db.fetch_all(sql, (tarifni_broj, limit))
