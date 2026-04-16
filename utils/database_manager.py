"""DatabaseManager - centralizovani menadžer za database konekcije sa connection pooling-om.

Obezbeđuje:
- Connection pooling za efikasno korišćenje konekcija
- Transaction management
- Error handling
- Logging
"""

import logging
from typing import Optional, Tuple, List, Union

import psycopg2
from psycopg2.extras import RealDictCursor

from config.settings import get_db_settings
from database.db import get_connection_pool

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Centralizovani menadžer za database konekcije sa connection pooling-om"""

    # Class-level connection pool
    _connection_pool = None

    @classmethod
    def get_pool(cls):
        """Kreira i vraća connection pool (lazy initialization)

        Returns:
            psycopg2.pool.SimpleConnectionPool or None
        """
        if cls._connection_pool is None:
            try:
                cls._connection_pool = get_connection_pool()
                logger.info("Connection pool uspešno kreiran")
            except Exception as e:
                logger.error(f"Greška pri kreiranju connection pool-a: {str(e)}")
                raise
        return cls._connection_pool

    @classmethod
    def get_connection(cls):
        """Kreira i vraća database konekciju iz pool-a

        Returns:
            psycopg2 connection object

        Raises:
            Exception: Ako konekcija ne uspe
        """
        try:
            pool = cls.get_pool()
            if pool:
                conn = pool.getconn()
                logger.debug("Database konekcija dobijena iz pool-a")
                return conn
            # Fallback ako pool nije kreiran — direktna konekcija (bez pooling-a)
            s = get_db_settings()
            conn = psycopg2.connect(
                host=s.host, port=s.port, database=s.database,
                user=s.user, password=s.password, cursor_factory=RealDictCursor
            )
            logger.debug("Database konekcija uspostavljena (fallback direktna)")
            return conn
        except Exception as e:
            logger.error(f"Greška pri dobijanju database konekcije: {str(e)}")
            raise Exception(f"Neuspešna database konekcija: {str(e)}")

    @classmethod
    def return_connection(cls, conn):
        """Vraća konekciju nazad u pool

        Args:
            conn: psycopg2 connection object za vraćanje
        """
        try:
            if cls._connection_pool:
                cls._connection_pool.putconn(conn)
                logger.debug("Database konekcija vraćena u pool")
            else:
                conn.close()
                logger.debug("Database konekcija zatvorena (nema pool-a)")
        except Exception as e:
            logger.error(f"Greška pri vraćanju konekcije: {str(e)}")

    @staticmethod
    def execute_query(
        query: str, params: Optional[Tuple] = None, fetch_all: bool = False
    ) -> Union[List[Tuple], Tuple, None]:
        """Izvršava SQL SELECT query i vraća rezultate

        Args:
            query: SQL query string
            params: Parametri za query (opciono)
            fetch_all: Ako je True vraća sve redove, inače samo prvi

        Returns:
            Query rezultati kao TUPLE (indeks pristup)
        """
        conn = None
        try:
            conn = DatabaseManager.get_connection()
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                if fetch_all:
                    result = cur.fetchall()
                    # Convert dict rows to tuples for backward compatibility
                    if result and isinstance(result[0], dict):
                        result = [tuple(row.values()) for row in result]
                    logger.debug(f"Query vraća {len(result)} redova")
                    return result
                result = cur.fetchone()
                # Convert dict row to tuple for backward compatibility
                if result and isinstance(result, dict):
                    result = tuple(result.values())
                logger.debug("Query vraća jedan red")
                return result
        except Exception as e:
            logger.error(f"Database query error: {str(e)}")
            raise Exception(f"Database query error: {str(e)}")
        finally:
            if conn:
                DatabaseManager.return_connection(conn)

    @staticmethod
    def execute_update(query: str, params: Optional[Tuple] = None) -> bool:
        """Izvršava UPDATE/INSERT/DELETE operacije

        Args:
            query: SQL query string
            params: Parametri za query (opciono)

        Returns:
            True ako operacija uspe

        Raises:
            Exception: Ako update ne uspe
        """
        conn = None
        try:
            conn = DatabaseManager.get_connection()
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                conn.commit()
                logger.info("Database update uspešan")
                return True
        except Exception as e:
            logger.error(f"Database update error: {str(e)}")
            raise Exception(f"Database update error: {str(e)}")
        finally:
            if conn:
                DatabaseManager.return_connection(conn)