"""
Validation Service - Validacija stavki
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
from core.draft import InvoiceLine
from services.validation.validation_service import FakturaItemValidator, ValidationResult
from services.agent.validation.evidence_model import evidence_from_preference


@dataclass
class RowValidationStyle:
    result: ValidationResult
    row_color: str = "#ffffff"
    row_tooltip: str = ""
    cell_overrides: dict[int, tuple[str, str]] = field(default_factory=dict)


class ValidationService:
    """Validacija i bojenje redova"""

    _COUNTRY_CONFIDENCE_COLORS = {
        "HIGH": "#d4edda",
        "MEDIUM": "#fff3cd",
        "LOW": "#ffe5d0",
        "CONFLICT": "#f8d7da",
    }
    # Pozadinske boje po STATIČKOJ grupi zemlje (country_preference_group) —
    # koriste se kad povlastica NIJE eksplicitno potvrđena za ovu stavku
    # (vidi country_confidence_style/preference_confidence_style). Cilj
    # (korisnički zahtjev 2026-08-02): CN/TW/BR/US i sl. (nikad povlašćene)
    # se ne smiju vizuelno miješati sa EU/CEFTA/TR-IR zemljama koje TEK
    # treba provjeriti — deklarant treba da ih odmah razlikuje u tabeli.
    # NONE zadržava staru _NEUTRAL_COUNTRY_COLOR vrijednost (najčešći slučaj,
    # minimalna vizuelna promjena za postojeće korisnike).
    _COUNTRY_GROUP_COLORS = {
        "EU": "#dde6f7",
        "CEFTA": "#ebe0f7",
        "OTHER_PREF": "#f7e8d4",
        "NONE": "#dfe4ea",
    }
    # Zadržano kao alias radi backward compatibility (drugi kod/testovi
    # mogu referencirati direktno) — vrijednost MORA ostati ista kao
    # _COUNTRY_GROUP_COLORS["NONE"].
    _NEUTRAL_COUNTRY_COLOR = _COUNTRY_GROUP_COLORS["NONE"]

    @staticmethod
    def country_group_color(country_code: str) -> str:
        """Pozadinska boja po grupi zemlje — vidi _COUNTRY_GROUP_COLORS."""
        from services.faktura.preference_rules_service import country_preference_group

        group = country_preference_group(country_code)
        return ValidationService._COUNTRY_GROUP_COLORS.get(group, ValidationService._NEUTRAL_COUNTRY_COLOR)

    @staticmethod
    def _pdf_oznaka_eligible_unset(item: InvoiceLine, country_code: str) -> bool:
        """Da li PDF ima samo oznaku zemlje (bez izjave o porijeklu), povlastica
        nije postavljena, a zemlja je uopšte podobna za neku povlasticu.

        DIJELJEN uslov između country_confidence_style i preference_
        confidence_style (korisnički zahtjev 2026-08-02: obje kolone moraju
        pokazati ISTU žutu boju u ovom stanju — ranije je samo Povlastica
        imala ovo upozorenje, Zemlja je za isti red pokazivala grupnu boju,
        što je izgledalo kao dvije nepovezane/neusklađene informacije).
        """
        from services.faktura.preference_rules_service import suggest_preference_by_country

        source = getattr(item, "country_source", None)
        has_pref = bool(item.povlastica)
        eligible_for_pref = bool(suggest_preference_by_country(country_code))
        return source == "PDF_OZNAKA" and not has_pref and eligible_for_pref

    @staticmethod
    def validation_issue_label(field: str, message: str) -> str:
        msg = (message or "").lower()
        if field == "tarifni_broj":
            return "bez tarife" if "obavezan" in msg else "neispravna tarifa"
        if field == "zemlja_porijekla":
            return "bez zemlje"
        if field == "naziv_robe":
            return "bez naziva robe"
        if field == "bruto":
            return "bruto < neto"
        if field == "cijena":
            return "cijena 0/negativna"
        return message or field or "nepoznata greška"

    def __init__(self):
        self.validator = FakturaItemValidator()

    def validate_and_get_color(self, item: InvoiceLine) -> Tuple[str, str]:
        """
        Validira stavku i vraća boju i tooltip.

        Args:
            item: InvoiceLine stavka

        Returns:
            Tuple: (color_hex, tooltip)
        """
        style = self.validate_and_get_style(item)
        return style.row_color, style.row_tooltip

    def validate_and_get_style(self, item: InvoiceLine) -> RowValidationStyle:
        result = self.validator.validate(item)
        tariff_sim = getattr(item, "tariff_similarity", 0.0) or 0.0

        # Check if item is UNMATCHED
        is_unmatched = (
            not item.tarifni_broj or len(item.tarifni_broj.strip()) == 0
        ) and (not item.zemlja_porijekla or len(item.zemlja_porijekla.strip()) == 0)

        # Determine color based on validation result
        cell_overrides: dict[int, tuple[str, str]] = {}
        if item.tarifni_broj and 0.70 <= tariff_sim < 0.92:
            color_hex = "#FFF4D6"
            tooltip = (
                f"⚠️ Tarifni broj: {item.tarifni_broj}\n"
                f"Pouzdanje: {tariff_sim:.0%}\n"
                f"Preporučuje se ručna provjera tarifnog broja"
            )
            cell_overrides[4] = (color_hex, tooltip)
            color_hex = "#ffffff"
            tooltip = ""
        elif is_unmatched:
            color_hex = "#E6F0F8"
            tooltip = "🔵 Nepodudarajuća stavka - nije pronađena u master listi. Popunite tarifni broj i zemlju porijekla."
            cell_overrides[4] = (color_hex, "❌ Nedostaje tarifni broj")
            cell_overrides[9] = (color_hex, "❌ Nedostaje zemlja porijekla")
            color_hex = "#ffffff"
            tooltip = ""
        elif not item.tarifni_broj or len(item.tarifni_broj.strip()) == 0:
            color_hex = "#F9E4E3"
            tooltip = "❌ Greška: Nedostaje tarifni broj"
            cell_overrides[4] = (color_hex, tooltip)
            color_hex = "#ffffff"
            tooltip = ""
        elif not item.zemlja_porijekla or len(item.zemlja_porijekla.strip()) == 0:
            color_hex = "#F9E4E3"
            tooltip = "❌ Greška: Nedostaje zemlja porijekla"
            cell_overrides[9] = (color_hex, tooltip)
            color_hex = "#ffffff"
            tooltip = ""
        elif result.has_blocking_errors():
            color_hex = "#F9E4E3"
            tooltip = "❌ Greška: " + "; ".join([e.message for e in (result.errors or [])])
        elif len(result.warnings or []) > 0:
            color_hex = "#FFF4D6"
            tooltip = "⚠️ Upozorenje: " + "; ".join([e.message for e in (result.warnings or [])])
        elif result.valid:
            color_hex = "#EAF4EE"
            tooltip = "✅ Validna stavka"
        else:
            color_hex = "#ffffff"  # White (not validated)
            tooltip = ""

        return RowValidationStyle(result, color_hex, tooltip, cell_overrides)

    def validate_all(self, items: List[InvoiceLine]) -> Dict[str, int]:
        """
        Validira sve stavke i vraća statistiku.

        Args:
            items: Lista InvoiceLine stavki

        Returns:
            Dict sa statistikom:
            {
                "error_count": int,
                "warning_count": int,
                "valid_count": int,
                "total_count": int
            }
        """
        error_count = 0
        warning_count = 0
        valid_count = 0

        for item in items:
            result = self.validator.validate(item)
            if result.has_blocking_errors():
                error_count += 1
            elif len(result.warnings or []) > 0:
                warning_count += 1
            elif result.valid:
                valid_count += 1

        return {
            "error_count": error_count,
            "warning_count": warning_count,
            "valid_count": valid_count,
            "total_count": len(items),
        }

    @staticmethod
    def count_issues_from_cache(validation_cache, row_indexes=None) -> dict:
        """Broji greške/upozorenja/validne iz cache-a, opciono skopirano na redove."""
        if row_indexes is not None:
            error_count = warning_count = valid_count = 0
            for row in row_indexes:
                result = validation_cache.get(row)
                if result is None:
                    continue
                if result.has_blocking_errors():
                    error_count += 1
                elif result.warnings:
                    warning_count += 1
                elif result.valid:
                    valid_count += 1
            return {
                "error_count": error_count,
                "warning_count": warning_count,
                "valid_count": valid_count,
                "total_count": len(row_indexes),
            }
        return {
            "error_count": validation_cache.get_error_count(),
            "warning_count": validation_cache.get_warning_count(),
            "valid_count": validation_cache.get_valid_count(),
            "total_count": validation_cache.total_count if hasattr(validation_cache, 'total_count') else 0,
        }

    @staticmethod
    def build_validation_message(counts: dict, error_issues: dict, warning_issues: dict,
                                  row_indexes=None) -> str:
        """Formatira validacioni message string."""
        message = ""
        if row_indexes is not None:
            message += f"📌 Prikazano samo za {len(row_indexes)} selektovanih stavki.\n\n"
        message += "╔══════════════════════════════════════╗\n"
        message += "║      REZULTAT VALIDACIJE             ║\n"
        message += "╠══════════════════════════════════════╣\n"
        message += f"║  Ukupno stavki: {counts['total_count']:>4}                ║\n"
        message += f"║  ✅ Validne:     {counts['valid_count']:>4}                ║\n"
        message += f"║  ❌ Nevažeće:    {counts['error_count']:>4}                ║\n"
        message += "╠══════════════════════════════════════╣\n"
        message += f"║  🔴 Greške:      {counts['error_count']:>4}                ║\n"
        message += f"║  🟡 Upozorenja:  {counts['warning_count']:>4}                ║\n"
        message += "╚══════════════════════════════════════╝\n"
        if error_issues:
            message += "\nGreške po tipu:\n"
            for label, count in sorted(error_issues.items(), key=lambda item: (-item[1], item[0])):
                message += f"  • {count} {label}\n"
        if warning_issues:
            message += "\nUpozorenja po tipu:\n"
            for label, count in sorted(warning_issues.items(), key=lambda item: (-item[1], item[0])):
                message += f"  • {count} {label}\n"
        return message

    @staticmethod
    def country_confidence_style(item: InvoiceLine) -> Optional[dict]:
        """
        Pravilo za bojenje/ikonicu kolone Zemlja porijekla.

        ✅/zelena (po nivou pouzdanosti) prati ISKLJUČIVO da li je povlastica
        EKSPLICITNO potvrđena za ovu konkretnu stavku (povlastica + prateći
        dokument: PE-šifra/EUR.1 broj/izjava o porijeklu) — ovaj dio pravila
        je nepromijenjen istorijski lock (vidi test_faktura_confidence_color_
        rules.py). Kad NIJE potvrđena, boja više NIJE flat neutralna za sve
        zemlje (stari obrazac) već prati STATIČKU grupu zemlje (EU/CEFTA/
        ostale povlašćene/nikad povlašćene, country_group_color) — korisnički
        zahtjev 2026-08-02, NEZAVISNO od country_confidence/pouzdanosti
        podatka (isti razlog kao ranije: teorijska podobnost NE smije
        izgledati kao potvrđena povlastica, pa se ✅/zelena ne dodjeljuje;
        grupa je samo vizuelna kategorizacija, ne tvrdnja o dokazu).

        Vraća None samo ako nema uopšte podatka o zemlji porijekla (ništa za
        obojiti) — RANIJE je vraćao None i kad je zemlja poznata ali
        country_confidence prazan (npr. Assembly/master-list stavke prije
        Faze detekcije porijekla), što je ostavljalo cijelu kolonu neobojenu
        za taj uvozni tok; to više NIJE slučaj.
        """
        zemlja = (getattr(item, "zemlja_porijekla", "") or "").strip()
        if not zemlja:
            return None

        preference = (getattr(item, "povlastica", "") or "").strip()
        evidence = evidence_from_preference(item)
        has_preferential_doc = bool(preference and not evidence.requires_confirmation)
        if has_preferential_doc:
            color_hex = ValidationService._COUNTRY_CONFIDENCE_COLORS.get(
                item.country_confidence, "#ffffff"
            )
            icon = "✅"
        elif ValidationService._pdf_oznaka_eligible_unset(item, zemlja):
            color_hex = "#fff3cd"
            icon = ""
        else:
            color_hex = ValidationService.country_group_color(zemlja)
            icon = ""
        neutral_country = not has_preferential_doc

        tooltip_parts = []
        if item.country_confidence == "HIGH":
            if item.country_source in ("PDF", "EXCEL"):
                tooltip_parts.append("✅ Podatak o poreklu iz uvezenog dokumenta (visoka pouzdanost)")
            elif item.country_source == "PDF_IZJAVA":
                tooltip_parts.append("✅ Podatak o poreklu iz izjave u dokumentu (visoka pouzdanost)")
            elif item.country_source == "PDF_OZNAKA":
                tooltip_parts.append("✅ Podatak o poreklu iz uvezenog dokumenta; povlasticu provjerava deklarant")
            elif item.country_source == "MATCH":
                tooltip_parts.append("✅ PDF i baza se poklapaju (visoka pouzdanost)")
            elif item.country_source == "EUR1_POTVRDA":
                tooltip_parts.append("✅ Porijeklo potvrđeno EUR.1 sertifikatom (visoka pouzdanost)")
            else:
                tooltip_parts.append("✅ Visoka pouzdanost")
        elif item.country_confidence == "MEDIUM":
            tooltip_parts.append("📋 Podatak o poreklu iz baze znanja (srednja pouzdanost)")
        elif item.country_confidence == "LOW":
            tooltip_parts.append("⚠️ Nema podataka o poreklu (potreban manuelni unos)")
        elif item.country_confidence == "CONFLICT":
            tooltip_parts.append(
                f"🚨 Konflikt porekla: {item.country_conflict_details or 'PDF i baza imaju različite vrednosti'}"
            )
            tooltip_parts.append("ℹ️ Korišćena je vrednost iz PDF-a")
        if neutral_country:
            tooltip_parts.append(
                "ℹ️ Povlastica za ovu stavku nije eksplicitno potvrđena."
            )

        return {"color_hex": color_hex, "icon": icon, "tooltip_parts": tooltip_parts}

    @staticmethod
    def preference_confidence_style(item: InvoiceLine) -> Optional[dict]:
        """
        Pravilo za bojenje/tooltip kolone Povlastica (odvojeno od kolone
        Zemlja porijekla).

        - žuto: povlastica namjerno NIJE postavljena, dokument ima samo
          oznaku zemlje (bez izjave), a zemlja je uopšte podobna za neku
          povlasticu — treba ručna provjera.
        - zeleno: povlastica izvedena iz potvrđenog porijekla (izjava/EUR.1/MATCH).
        - boja po grupi zemlje (EU/CEFTA/ostale povlašćene): nijedan od gornja
          dva uslova ne važi, ALI je zemlja teorijski podobna za povlasticu —
          isti obrazac kao country_confidence_style (korisnički zahtjev
          2026-08-02), da deklarant odmah uoči koje stavke treba provjeriti.
        - None: zemlja nikad nema povlasticu (npr. CN — country_preference_
          group == NONE) ili nije uopšte poznata — ćelija ostaje bez izmjene
          (namjerno, vidi test_pdf_oznaka_bez_povlastice_neeligible_zemlja_
          bez_upozorenja — upozorenje/isticanje na nepodobnoj zemlji je
          besmisleno).
        """
        from services.faktura.preference_rules_service import country_preference_group

        evidence = evidence_from_preference(item)
        has_pref = bool(item.povlastica)
        country_code = (getattr(item, "zemlja_porijekla", "") or "").strip()

        if ValidationService._pdf_oznaka_eligible_unset(item, country_code):
            return {
                "color_hex": "#fff3cd",
                "tooltip": (
                    "⚠️ Povlastica NIJE automatski postavljena — dokument sadrži "
                    "samo oznaku zemlje porijekla, bez izjave o porijeklu.\n"
                    "Provjerite ručno da li roba ima pravo na povlasticu i unesite je."
                ),
            }
        if has_pref and not evidence.requires_confirmation:
            return {
                "color_hex": "#d4edda",
                "tooltip": (
                    "✅ Povlastica je potvrđena PE1/PE2/PE3 dokazom.\n"
                    "Provjerite da li odgovara podacima na fakturi."
                ),
            }
        if country_code and country_preference_group(country_code) != "NONE":
            return {
                "color_hex": ValidationService.country_group_color(country_code),
                "tooltip": (
                    "ℹ️ Zemlja je potencijalno podobna za povlasticu — "
                    "provjerite dokaz porijekla."
                ),
            }
        return None
