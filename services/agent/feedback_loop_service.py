"""
Feedback Loop Service

Učenje iz korisničkih odluka:
1. Kada korisnik prihvati/odbije predlog
2. Kada korisnik ručno koriguje povlasticu
3. Poboljšanje predloga na osnovu feedback-a
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import json

from database.db import get_db_connection
from services.tariff_mapping_service import TariffMapping

logger = logging.getLogger("asycuda_pro.feedback_loop")


@dataclass
class FeedbackItem:
    """Jedan feedback item."""
    id: Optional[int]
    user_id: str  # "default" za sada (može se proširiti za multi-user)
    action_type: str  # 'accept', 'reject', 'correct', 'override'
    item_type: str  # 'preference', 'tariff', 'country', 'supplier'
    item_key: str  # Ključ itema (npr. 'supplier:ZORKA KERAMIKA:country:RS')
    original_value: str  # Originalna vrijednost (predlog)
    new_value: str  # Nova vrijednost (korisnički unos)
    confidence: float  # Confidence originalnog predloga
    context: Dict[str, Any]  # Dodatni kontekst
    created_at: datetime
    processed: bool  # Da li je feedback već procesiran za učenje


@dataclass
class FeedbackStats:
    """Statistika feedback-a."""
    total_feedback: int
    by_action_type: Dict[str, int]
    by_item_type: Dict[str, int]
    acceptance_rate: float  # accept / (accept + reject)
    avg_confidence: float


class FeedbackLoopService:
    """
    Feedback Loop Service za učenje iz korisničkih odluka.
    
    Karakteristike:
    1. Consent-based (korisnik mora pristati)
    2. Background processing
    3. Incremental learning
    4. Privacy-aware (anonymized data)
    """
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.user_consent = False  # Po defaultu nema consent
        
        # Cache za brži pristup
        self.feedback_cache: Dict[str, List[FeedbackItem]] = {}
        
        logger.info(f"✅ FeedbackLoopService inicijalizovan (enabled: {enabled})")
    
    def set_user_consent(self, consent: bool):
        """Postavi user consent."""
        self.user_consent = consent
        logger.info(f"📝 User consent set to: {consent}")
    
    def record_feedback(
        self,
        action_type: str,
        item_type: str,
        item_key: str,
        original_value: str,
        new_value: str,
        confidence: float = 1.0,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Zabilježi feedback od korisnika.
        
        Args:
            action_type: 'accept', 'reject', 'correct', 'override'
            item_type: 'preference', 'tariff', 'country', 'supplier'
            item_key: Ključ za identifikaciju itema
            original_value: Originalni predlog
            new_value: Korisnički unos
            confidence: Confidence originalnog predloga
            context: Dodatni kontekst
        
        Returns:
            True ako je feedback zabilježen, False ako nije (nema consent)
        """
        if not self.enabled or not self.user_consent:
            logger.debug(f"⚠️ Feedback not recorded (enabled: {self.enabled}, consent: {self.user_consent})")
            return False
        
        try:
            feedback = FeedbackItem(
                id=None,
                user_id="default",  # Za sada single user
                action_type=action_type,
                item_type=item_type,
                item_key=item_key,
                original_value=original_value,
                new_value=new_value,
                confidence=confidence,
                context=context or {},
                created_at=datetime.now(),
                processed=False
            )
            
            # Sačuvaj u bazi
            self._save_feedback_to_db(feedback)
            
            # Dodaj u cache
            if item_key not in self.feedback_cache:
                self.feedback_cache[item_key] = []
            self.feedback_cache[item_key].append(feedback)
            
            logger.debug(f"📝 Feedback recorded: {action_type} for {item_type} '{item_key}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error recording feedback: {e}")
            return False
    
    def _save_feedback_to_db(self, feedback: FeedbackItem):
        """Sačuvaj feedback u bazi podataka."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO catalogs.user_feedback 
                        (user_id, action_type, item_type, item_key, 
                         original_value, new_value, confidence, context, 
                         created_at, processed)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        feedback.user_id,
                        feedback.action_type,
                        feedback.item_type,
                        feedback.item_key,
                        feedback.original_value,
                        feedback.new_value,
                        feedback.confidence,
                        json.dumps(feedback.context),
                        feedback.created_at,
                        feedback.processed
                    ))
                    
                    feedback.id = cursor.fetchone()['id']
                    conn.commit()
                    
        except Exception as e:
            # Ako tabela ne postoji, kreiraj je
            if "relation \"catalogs.user_feedback\" does not exist" in str(e):
                self._create_feedback_table()
                # Pokušaj ponovo
                self._save_feedback_to_db(feedback)
            else:
                raise
    
    def _create_feedback_table(self):
        """Kreiraj feedback tabelu ako ne postoji."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS catalogs.user_feedback (
                            id SERIAL PRIMARY KEY,
                            user_id VARCHAR(100) NOT NULL DEFAULT 'default',
                            action_type VARCHAR(50) NOT NULL,
                            item_type VARCHAR(50) NOT NULL,
                            item_key VARCHAR(500) NOT NULL,
                            original_value TEXT,
                            new_value TEXT,
                            confidence FLOAT DEFAULT 1.0,
                            context JSONB,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            processed BOOLEAN DEFAULT FALSE,
                            UNIQUE(user_id, item_key, action_type, created_at)
                        );
                        
                        CREATE INDEX IF NOT EXISTS idx_user_feedback_item_key 
                        ON catalogs.user_feedback(item_key);
                        
                        CREATE INDEX IF NOT EXISTS idx_user_feedback_processed 
                        ON catalogs.user_feedback(processed) WHERE NOT processed;
                    """)
                    conn.commit()
                    
                    logger.info("✅ Created user_feedback table")
                    
        except Exception as e:
            logger.error(f"❌ Error creating feedback table: {e}")
    
    def get_feedback_for_item(self, item_key: str) -> List[FeedbackItem]:
        """Dobavi sve feedback za određeni item."""
        # Prvo provjeri cache
        if item_key in self.feedback_cache:
            return self.feedback_cache[item_key]
        
        # Učitaj iz baze
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, user_id, action_type, item_type, item_key,
                               original_value, new_value, confidence, context,
                               created_at, processed
                        FROM catalogs.user_feedback
                        WHERE item_key = %s
                        ORDER BY created_at DESC
                        LIMIT 100
                    """, (item_key,))
                    
                    feedback_items = []
                    for row in cursor.fetchall():
                        feedback = FeedbackItem(
                            id=row['id'],
                            user_id=row['user_id'],
                            action_type=row['action_type'],
                            item_type=row['item_type'],
                            item_key=row['item_key'],
                            original_value=row['original_value'],
                            new_value=row['new_value'],
                            confidence=row['confidence'],
                            context=json.loads(row['context']) if row['context'] else {},
                            created_at=row['created_at'],
                            processed=row['processed']
                        )
                        feedback_items.append(feedback)
                    
                    # Sačuvaj u cache
                    self.feedback_cache[item_key] = feedback_items
                    
                    return feedback_items
                    
        except Exception as e:
            logger.debug(f"⚠️ Error getting feedback for {item_key}: {e}")
            return []
    
    def get_feedback_stats(self) -> FeedbackStats:
        """Dobavi statistiku feedback-a."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Ukupno feedback
                    cursor.execute("SELECT COUNT(*) as total FROM catalogs.user_feedback")
                    total = cursor.fetchone()['total']
                    
                    # Po action type
                    cursor.execute("""
                        SELECT action_type, COUNT(*) as count
                        FROM catalogs.user_feedback
                        GROUP BY action_type
                    """)
                    by_action = {row['action_type']: row['count'] for row in cursor.fetchall()}
                    
                    # Po item type
                    cursor.execute("""
                        SELECT item_type, COUNT(*) as count
                        FROM catalogs.user_feedback
                        GROUP BY item_type
                    """)
                    by_item = {row['item_type']: row['count'] for row in cursor.fetchall()}
                    
                    # Acceptance rate
                    accept_count = by_action.get('accept', 0)
                    reject_count = by_action.get('reject', 0)
                    total_decisions = accept_count + reject_count
                    acceptance_rate = accept_count / total_decisions if total_decisions > 0 else 0.0
                    
                    # Prosječan confidence
                    cursor.execute("SELECT AVG(confidence) as avg_conf FROM catalogs.user_feedback")
                    avg_confidence = cursor.fetchone()['avg_conf'] or 0.0
                    
                    return FeedbackStats(
                        total_feedback=total,
                        by_action_type=by_action,
                        by_item_type=by_item,
                        acceptance_rate=acceptance_rate,
                        avg_confidence=avg_confidence
                    )
                    
        except Exception as e:
            logger.debug(f"⚠️ Error getting feedback stats: {e}")
            return FeedbackStats(
                total_feedback=0,
                by_action_type={},
                by_item_type={},
                acceptance_rate=0.0,
                avg_confidence=0.0
            )
    
    def process_pending_feedback(self) -> int:
        """
        Procesiraj pending feedback za učenje.
        
        Ova metoda treba da se poziva u background thread-u.
        
        Returns:
            Broj procesiranih feedback itema
        """
        if not self.enabled:
            return 0
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Dobavi pending feedback
                    cursor.execute("""
                        SELECT id, action_type, item_type, item_key,
                               original_value, new_value, confidence, context
                        FROM catalogs.user_feedback
                        WHERE NOT processed
                        ORDER BY created_at
                        LIMIT 100
                    """)
                    
                    processed_count = 0
                    
                    for row in cursor.fetchall():
                        try:
                            # Procesiraj feedback ovisno o tipu
                            if row['item_type'] == 'preference':
                                self._process_preference_feedback(row)
                            elif row['item_type'] == 'tariff':
                                self._process_tariff_feedback(row)
                            elif row['item_type'] == 'supplier':
                                self._process_supplier_feedback(row)
                            
                            # Označi kao procesirano
                            cursor.execute(
                                "UPDATE catalogs.user_feedback SET processed = TRUE WHERE id = %s",
                                (row['id'],)
                            )
                            
                            processed_count += 1
                            
                        except Exception as e:
                            logger.error(f"❌ Error processing feedback {row['id']}: {e}")
                            # Označi kao procesirano da ne blokira dalje procesiranje
                            cursor.execute(
                                "UPDATE catalogs.user_feedback SET processed = TRUE WHERE id = %s",
                                (row['id'],)
                            )
                    
                    conn.commit()
                    
                    if processed_count > 0:
                        logger.info(f"✅ Processed {processed_count} feedback items")
                    
                    return processed_count
                    
        except Exception as e:
            logger.error(f"❌ Error processing pending feedback: {e}")
            return 0
    
    def _process_preference_feedback(self, feedback_row: Dict):
        """Procesiraj feedback za povlastice."""
        action_type = feedback_row['action_type']
        item_key = feedback_row['item_key']
        new_value = feedback_row['new_value']
        context = json.loads(feedback_row['context']) if feedback_row['context'] else {}
        
        # Parsiraj item_key (format: 'supplier:NAME:country:CODE')
        parts = item_key.split(':')
        if len(parts) >= 4 and parts[0] == 'supplier' and parts[2] == 'country':
            supplier = parts[1]
            country = parts[3]
            
            if action_type == 'accept':
                # Korisnik je prihvatio predlog - povećaj confidence
                logger.debug(f"📈 Preference accepted: {supplier} + {country} → {new_value}")
                
            elif action_type == 'reject':
                # Korisnik je odbio predlog - smanji confidence
                logger.debug(f"📉 Preference rejected: {supplier} + {country} → {new_value}")
                
            elif action_type == 'correct':
                # Korisnik je korigovao - učimo novu vrijednost
                logger.debug(f"📝 Preference corrected: {supplier} + {country} → {new_value}")
                
                # TODO: Ažuriraj historijske podatke
                # Možemo ažurirati supplier_historical_profiles tabelu
    
    def _process_tariff_feedback(self, feedback_row: Dict):
        """Procesiraj feedback za tarifne brojeve."""
        action_type = feedback_row['action_type']
        item_key = feedback_row['item_key']
        new_value = feedback_row['new_value']
        
        # Parsiraj item_key (format: 'product:CODE' ili 'supplier:NAME:product:DESC')
        if action_type == 'accept':
            logger.debug(f"📈 Tariff accepted: {item_key} → {new_value}")
            
        elif action_type == 'correct':
            logger.debug(f"📝 Tariff corrected: {item_key} → {new_value}")
            
            # TODO: Ažuriraj product_tariff_mapping
            # Povećaj usage_count za ovaj mapping
    
    def _process_supplier_feedback(self, feedback_row: Dict):
        """Procesiraj feedback za suppliere."""
        action_type = feedback_row['action_type']
        item_key = feedback_row['item_key']
        
        if action_type == 'correct':
            # Korisnik je korigovao ime suppliera
            old_supplier = item_key.replace('supplier:', '')
            new_supplier = feedback_row['new_value']
            
            logger.debug(f"📝 Supplier corrected: {old_supplier} → {new_supplier}")
            
            # TODO: Ažuriraj exporter_xml_index za rename
    
    def get_recommendation_with_feedback(
        self,
        item_type: str,
        item_key: str,
        original_recommendation: str,
        original_confidence: float = 1.0
    ) -> Tuple[str, float, str]:
        """
        Dobavi preporuku uzimajući u obzir historijski feedback.
        
        Args:
            item_type: Tip itema ('preference', 'tariff', 'country')
            item_key: Ključ itema
            original_recommendation: Originalna preporuka
            original_confidence: Originalni confidence
        
        Returns:
            Tuple: (final_recommendation, adjusted_confidence, explanation)
        """
        if not self.enabled:
            return original_recommendation, original_confidence, "No feedback processing"
        
        feedback_items = self.get_feedback_for_item(item_key)
        
        if not feedback_items:
            return original_recommendation, original_confidence, "No feedback history"
        
        # Analiziraj feedback historiju
        accept_count = sum(1 for f in feedback_items if f.action_type == 'accept')
        reject_count = sum(1 for f in feedback_items if f.action_type == 'reject')
        correct_count = sum(1 for f in feedback_items if f.action_type == 'correct')
        
        total_feedback = len(feedback_items)
        
        if correct_count > 0:
            # Ako je korisnik korigovao, koristi posljednju korekciju
            last_correction = next(
                (f for f in reversed(feedback_items) if f.action_type == 'correct'),
                None
            )
            if last_correction:
                adjusted_confidence = min(original_confidence + 0.2, 1.0)  # Bonus za korekciju
                explanation = f"Korisnik je korigovao {correct_count} puta (zadnje: {last_correction.new_value})"
                return last_correction.new_value, adjusted_confidence, explanation
        
        # Ako nema korekcija, analiziraj accept/reject ratio
        if total_feedback > 0:
            acceptance_ratio = accept_count / total_feedback
            
            if acceptance_ratio >= 0.7:  # Visok acceptance rate
                adjusted_confidence = min(original_confidence + 0.1, 1.0)
                explanation = f"Visok acceptance rate ({acceptance_ratio:.0%})"
                return original_recommendation, adjusted_confidence, explanation
            
            elif acceptance_ratio <= 0.3:  # Nizak acceptance rate
                adjusted_confidence = max(original_confidence - 0.2, 0.1)
                explanation = f"Nizak acceptance rate ({acceptance_ratio:.0%})"
                return original_recommendation, adjusted_confidence, explanation
        
        # Default: vrati original
        return original_recommendation, original_confidence, f"{total_feedback} feedback items analyzed"
    
    def clear_feedback_cache(self):
        """Očisti feedback cache."""
        self.feedback_cache.clear()
        logger.debug("🧹 Feedback cache cleared")
    
    def export_feedback_data(self, anonymize: bool = True) -> List[Dict]:
        """Izvezi feedback podatke (za analizu ili backup)."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, action_type, item_type, item_key,
                               original_value, new_value, confidence,
                               created_at, processed
                        FROM catalogs.user_feedback
                        ORDER BY created_at DESC
                        LIMIT 1000
                    """)
                    
                    data = []
                    for row in cursor.fetchall():
                        item = dict(row)
                        
                        if anonymize:
                            # Anonymizuj user_id
                            item['user_id'] = 'anonymous'
                            # Ukloni sensitive data iz context-a
                            if 'context' in item and item['context']:
                                context = json.loads(item['context'])
                                # Ukloni potencijalno sensitive podatke
                                context.pop('invoice_number', None)
                                context.pop('personal_data', None)
                                item['context'] = json.dumps(context)
                        
                        data.append(item)
                    
                    return data
                    
        except Exception as e:
            logger.error(f"❌ Error exporting feedback data: {e}")
            return []


# Helper funkcije za integraciju

def create_feedback_key_preference(supplier: str, country: str) -> str:
    """Kreiraj feedback key za povlasticu."""
    return f"supplier:{supplier}:country:{country}"


def create_feedback_key_tariff(product_code: str, product_name: str) -> str:
    """Kreiraj feedback key za tarifni broj."""
    if product_code:
        return f"product:{product_code}"
    else:
        # Koristi hash naziva ako nema product_code
        import hashlib
        name_hash = hashlib.md5(product_name.encode()).hexdigest()[:8]
        return f"product_name:{name_hash}"


def create_feedback_key_supplier(supplier: str) -> str:
    """Kreiraj feedback key za suppliera."""
    return f"supplier:{supplier}"


# Test funkcija
def test_feedback_loop():
    """Test feedback loop servisa."""
    print("🧪 Testiranje FeedbackLoopService...")
    
    service = FeedbackLoopService(enabled=True)
    service.set_user_consent(True)
    
    # Test 1: Record feedback
    print("\n1. Test record feedback:")
    
    key1 = create_feedback_key_preference("ZORKA KERAMIKA", "RS")
    success1 = service.record_feedback(
        action_type="accept",
        item_type="preference",
        item_key=key1,
        original_value="CEFTAP",
        new_value="CEFTAP",
        confidence=0.8,
        context={"invoice": "FAI-7-0/26", "user_action": "clicked_accept"}
    )
    print(f"   ✅ Feedback recorded: {success1}")
    
    # Test 2: Get feedback stats
    print("\n2. Test feedback stats:")
    stats = service.get_feedback_stats()
    print(f"   Total feedback: {stats.total_feedback}")
    print(f"   By action type: {stats.by_action_type}")
    print(f"   Acceptance rate: {stats.acceptance_rate:.1%}")
    
    # Test 3: Get recommendation with feedback
    print("\n3. Test recommendation with feedback:")
    rec, conf, expl = service.get_recommendation_with_feedback(
        item_type="preference",
        item_key=key1,
        original_recommendation="CEFTAP",
        original_confidence=0.8
    )
    print(f"   Recommendation: {rec}")
    print(f"   Confidence: {conf:.1%}")
    print(f"   Explanation: {expl}")
    
    # Test 4: Process pending feedback
    print("\n4. Test process pending feedback:")
    processed = service.process_pending_feedback()
    print(f"   Processed items: {processed}")
    
    print("\n✅ Feedback loop testiran!")


if __name__ == "__main__":
    test_feedback_loop()