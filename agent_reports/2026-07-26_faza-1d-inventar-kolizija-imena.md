# Faza −1.D — Inventar kolizija imena validacionih tipova

**Plan**: `docs/agent/AGENT_V2_IMPLEMENTACIONI_PLAN.md` §3.7 i §10 −1.D
**Datum**: 2026-07-26
**Agent**: Pi

---

## 8 konkurentnih „je li u redu" reprezentacija

| # | Tip | Lokacija | Polje ishoda | Import putanja |
|---|-----|----------|-------------|----------------|
| 1 | `ValidationResult` | `services/validation/validation_service.py:31` | `valid`, `has_blocking_errors()` | `from services.validation.validation_service import ValidationResult` |
| 2 | `ValidationResult` **(druga klasa, isto ime!)** | `services/validation/preference_validator.py:19` | — | `from services.validation.preference_validator import ValidationResult` |
| 3 | `ValidationItem` + `ValidationReport` | `services/agent/validation/declaration_validator_service.py:54,72` | `valid` | `from services.agent.validation.declaration_validator_service import ValidationItem, ValidationReport` |
| 4 | `Issue` + `ComplianceResult` | `services/agent/validation/declaration_validator_service.py:751,759` | — | `from services.agent.validation.declaration_validator_service import Issue, ComplianceResult` |
| 5 | `NaimenovanjeValidation` | `services/agent/validation/naimenovanja_review_service.py:25` | — | `from services.agent.validation.naimenovanja_review_service import NaimenovanjeValidation` |
| 6 | `PipelineStageResult` | `gui/tabs/agent/services/pipeline_stage_result.py` | `status`, `can_continue` | `from gui.tabs.agent.services.pipeline_stage_result import PipelineStageResult` |
| 7 | `ToolResult` | `services/agent/chat/tool_result.py` | `status`, `can_llm_infer` | `from services.agent.chat.tool_result import ToolResult` |
| 8 | `overall_outcome()` → `str` | `gui/tabs/agent/services/pipeline_stage_result.py` | `COMPLETED/PARTIAL/FAILED/CANCELLED` | `from gui.tabs.agent.services.pipeline_stage_result import overall_outcome` |

---

## 5 kolizija imena `ValidationError`

| # | Tip | Lokacija |
|---|-----|----------|
| 1 | `ValidationError` (dataclass) | `services/validation/validation_service.py:21` |
| 2 | `ValidationError` (Exception) | `utils/exceptions.py:28` |
| 3 | `ValidationError` (Exception) | `importers/exceptions.py:116` |
| 4 | `ValidationError` (Exception) | `services/core/exceptions.py:11` |
| 5 | `ValidationError` (Exception) | `services/core/base_service.py:32` |

---

## Obavezni alias u Fazi 2 adapterima

Svaki adapter iz Faze 2 koji uvozi ove tipove MORA koristiti alias:

```python
from services.validation.validation_service import ValidationResult as FakturaValidationResult
from services.validation.preference_validator import ValidationResult as PreferenceValidationResult
from services.agent.validation.declaration_validator_service import (
    ValidationItem as DeclarationValidationItem,
    ValidationReport as DeclarationValidationReport,
)
```
