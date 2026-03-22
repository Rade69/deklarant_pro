"""
Batch Processor - Masovno popunjavanje tarifnih brojeva.

Koristi HybridTariffAgent za auto-popunu svih naimenovanja
kojima nedostaje tarifni broj.
"""

from typing import Dict, List, Any, Optional
from services.agent.hybrid_tariff_agent import HybridTariffAgent


class BatchProcessor:
    """
    Procesor za batch popunjavanje tarifnih brojeva.
    
    Features:
    - Process all items without tariff code
    - Progress tracking
    - Statistics (auto-filled, needs_review, failed)
    - Cancel support
    """
    
    def __init__(self):
        self.agent = HybridTariffAgent()
        self.cancelled = False
    
    def process_items(
        self,
        items: List[Dict[str, Any]],
        progress_callback=None,
        log_callback=None
    ) -> Dict[str, Any]:
        """
        Process all items and suggest tariff codes.
        
        Args:
            items: Lista stavki sa 'goods_trade_name' i 'origin_country_code'
            progress_callback: Callback za progress (current, total)
            log_callback: Callback za log poruke
            
        Returns:
            Dict sa:
            - auto_filled: Broj automatski popunjenih
            - needs_review: Broj onih sa niskim confidence
            - failed: Broj neuspjelih
            - results: Detaljni rezultati po stavkama
        """
        self.cancelled = False
        
        total = len(items)
        auto_filled = 0
        needs_review = 0
        failed = 0
        results = []
        
        for i, item in enumerate(items):
            # Check for cancellation
            if self.cancelled:
                if log_callback:
                    log_callback("⚠️ Prekinuto od strane korisnika")
                break
            
            # Progress
            if progress_callback:
                progress_callback(i + 1, total)
            
            # Get item data
            naziv_robe = item.get('goods_trade_name', '') or item.get('naziv_robe', '')
            zemlja = item.get('origin_country_code', '') or item.get('zemlja_porijekla', '')
            
            # Skip if no goods name
            if not naziv_robe:
                failed += 1
                results.append({
                    'index': i,
                    'status': 'failed',
                    'reason': 'Nema naziva robe',
                    'tariff_code': None
                })
                if log_callback:
                    log_callback(f"❌ Stavka {i+1}: Nema naziva robe")
                continue
            
            # Process with AI agent
            result = self.agent.decide_tariff(naziv_robe, zemlja)
            
            tariff_code = result.get('tarifni_broj', '')
            confidence = result.get('confidence', 0)
            needs_review_flag = result.get('needs_review', False)
            
            if tariff_code:
                if confidence >= 0.85 and not needs_review_flag:
                    # Auto-fill
                    auto_filled += 1
                    status = 'auto_filled'
                    if log_callback:
                        log_callback(f"✅ Stavka {i+1}: {naziv_robe[:40]}... → {tariff_code} ({confidence:.0%})")
                else:
                    # Needs review
                    needs_review += 1
                    status = 'needs_review'
                    if log_callback:
                        log_callback(f"⚠️ Stavka {i+1}: {naziv_robe[:40]}... → {tariff_code} ({confidence:.0%}, needs review)")
                
                results.append({
                    'index': i,
                    'status': status,
                    'tariff_code': tariff_code,
                    'confidence': confidence,
                    'method': result.get('method', 'unknown'),
                    'explanation': result.get('explanation', '')
                })
            else:
                failed += 1
                results.append({
                    'index': i,
                    'status': 'failed',
                    'reason': 'Nema prijedloga',
                    'tariff_code': None
                })
                if log_callback:
                    log_callback(f"❌ Stavka {i+1}: Nema prijedloga za '{naziv_robe[:40]}...'")
        
        return {
            'auto_filled': auto_filled,
            'needs_review': needs_review,
            'failed': failed,
            'total': total,
            'results': results,
            'success_rate': (auto_filled + needs_review) / total * 100 if total > 0 else 0
        }
    
    def cancel(self):
        """Prekini procesiranje."""
        self.cancelled = True
    
    def reset(self):
        """Resetuj processor za novi batch."""
        self.cancelled = False
