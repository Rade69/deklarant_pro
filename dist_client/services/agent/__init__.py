# services/agent/__init__.py
# Re-exports za backward compatibility — vanjski importi ostaju nepromijenjeni.

# chat/
from services.agent.chat.intent_classifier import IntentClassifier
from services.agent.chat.chat_memory_service import ChatMemoryService
from services.agent.chat.tariff_intent_service import TariffIntentService
from services.agent.chat.naimenovanja_intent_service import NaimenovanjaIntentService
from services.agent.chat.merge_intent_service import MergeIntentService
from services.agent.chat.declaration_search_service import DeclarationSearchService

# learning/
from services.agent.learning.historical_learning_service_safe import (
    HistoricalLearningServiceSafe,
    HistoricalLearningService,
    enhance_preference_logic,
    get_historical_service,
)
from services.agent.learning.exporter_xml_indexer import find_xml_for_pair
from services.agent.learning.supplier_profiling_service import SupplierProfilingService

# validation/
from services.agent.validation.declaration_validator_service import (
    DeclarationValidatorService,
    ComplianceCheckService,
)
from services.agent.validation.naimenovanja_review_service import NaimenovanjaReviewService
from services.agent.validation.xml_template_service import XmlTemplateService

# tariff/
from services.agent.tariff.hybrid_tariff_agent import HybridTariffAgent
from services.agent.tariff.tariff_rag_service import TariffRAGService
from services.agent.tariff.tariff_suggestion_service import HybridMatchingService, EnhancedTariffSuggestionService

__all__ = [
    # chat
    "IntentClassifier", "ChatMemoryService", "TariffIntentService",
    "NaimenovanjaIntentService", "MergeIntentService", "DeclarationSearchService",
    # learning
    "HistoricalLearningServiceSafe", "HistoricalLearningService",
    "enhance_preference_logic", "get_historical_service",
    "find_xml_for_pair", "SupplierProfilingService",
    # validation
    "DeclarationValidatorService", "ComplianceCheckService",
    "NaimenovanjaReviewService", "XmlTemplateService",
    # tariff
    "HybridTariffAgent", "TariffRAGService",
    "HybridMatchingService", "EnhancedTariffSuggestionService",
]
