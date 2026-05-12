"""
Offline testovi za Tool Use sistem — ne zavise od DeepSeek API-ja.

Testira:
- _execute_tool() mapiranje na servise (sa mock controller-om)
- TOOLS schema validaciju (svi alati imaju ispravan JSON schema)
- SYSTEM_PROMPT pokriva sve alate

📄 Povezano: docs/decisions/001-tool-use-refactoring.md
   Zavisnosti: services/agent/chat/tool_definitions.py
              gui/tabs/agent/services/chat_intent_handler.py
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ── TOOLS schema validacija ──────────────────────────────────────────

class TestToolSchema:
    """Validacija strukture TOOLS definicija."""

    @pytest.fixture(autouse=True)
    def _load_tools(self):
        from services.agent.chat.tool_definitions import TOOLS, SYSTEM_PROMPT
        self.TOOLS = TOOLS
        self.SYSTEM_PROMPT = SYSTEM_PROMPT

    def test_svi_alati_imaju_obavezna_polja(self):
        """Svaki alat mora imati type=function, name, description, parameters."""
        for tool in self.TOOLS:
            assert tool["type"] == "function", f"Alat {tool} nema type=function"
            func = tool["function"]
            assert "name" in func, f"Alat {func} nema name"
            assert "description" in func, f"Alat {func.get('name')} nema description"
            assert "parameters" in func, f"Alat {func.get('name')} nema parameters"

    def test_nazivi_alata_su_jedinstveni(self):
        """Nijedan alat ne smije imati duplikat imena."""
        names = [t["function"]["name"] for t in self.TOOLS]
        assert len(names) == len(set(names)), f"Duplikat imena: {names}"

    def test_parametri_su_validan_json_schema(self):
        """Svaki alat mora imati ispravan JSON schema za parameters."""
        for tool in self.TOOLS:
            func = tool["function"]
            params = func["parameters"]
            assert params["type"] == "object", \
                f"{func['name']}: parameters.type mora biti 'object'"
            assert "properties" in params, \
                f"{func['name']}: parameters mora imati 'properties'"
            assert "additionalProperties" in params, \
                f"{func['name']}: parameters mora imati 'additionalProperties'"

    def test_required_su_podskup_properties(self):
        """Ako alat ima required polja, moraju biti u properties."""
        for tool in self.TOOLS:
            func = tool["function"]
            params = func["parameters"]
            if "required" in params:
                for req in params["required"]:
                    assert req in params["properties"], \
                        f"{func['name']}: required '{req}' nije u properties"

    def test_enum_vrijednosti_su_validne(self):
        """Enum polja moraju imati barem jednu vrijednost."""
        for tool in self.TOOLS:
            func = tool["function"]
            for prop_name, prop in func["parameters"]["properties"].items():
                if "enum" in prop:
                    assert len(prop["enum"]) > 0, \
                        f"{func['name']}.{prop_name}: enum ne smije biti prazan"

    def test_ima_tacno_9_alata(self):
        """Trenutno imamo 9 definisanih alata."""
        assert len(self.TOOLS) == 9, \
            f"Očekivano 9 alata, dobijeno {len(self.TOOLS)}. Ako dodaješ alat, ažuriraj ovaj test."

    def test_system_prompt_pominje_sve_alate(self):
        """System prompt treba da sadrži instrukcije za svaki alat."""
        tool_names = [t["function"]["name"] for t in self.TOOLS]
        for name in tool_names:
            assert name in self.SYSTEM_PROMPT, \
                f"SYSTEM_PROMPT ne pominje alat '{name}'"

    def test_alati_imaju_minimalan_opis(self):
        """Opis alata treba da ima barem 30 karaktera."""
        for tool in self.TOOLS:
            func = tool["function"]
            assert len(func["description"]) >= 30, \
                f"{func['name']}: opis prekratak ({len(func['description'])} znakova)"


# ── _execute_tool mapiranje ──────────────────────────────────────────

class TestExecuteToolMapping:
    """Testira mapiranje tool name → servisni poziv."""

    @pytest.fixture
    def mock_ctrl(self):
        """Kreira mock controller sa svim potrebnim servisima."""
        ctrl = MagicMock()
        ctrl.view = MagicMock()
        ctrl.view.get_chat_panel = MagicMock()
        ctrl.draft = MagicMock()
        ctrl.tariff_svc = MagicMock()
        ctrl.naim_intent_svc = MagicMock()
        return ctrl

    def _call_execute(self, ctrl, name, args=None):
        from gui.tabs.agent.services.chat_intent_handler import _execute_tool
        _execute_tool(ctrl, name, args or {})

    # ── predlozi_tarife ──

    def test_predlozi_tarife_batch(self, mock_ctrl):
        self._call_execute(mock_ctrl, "predlozi_tarife", {})
        mock_ctrl._predlozi_tarifne_brojeve.assert_called_once()

    def test_predlozi_tarife_sa_filterom(self, mock_ctrl):
        self._call_execute(mock_ctrl, "predlozi_tarife", {"filter": "čelik"})
        mock_ctrl.tariff_svc.propose_by_keyword.assert_called_once_with("čelik")

    # ── provjeri_tarife ──

    def test_provjeri_tarife(self, mock_ctrl):
        self._call_execute(mock_ctrl, "provjeri_tarife", {})
        # _provjeri_naimenovanja je pozvana — provjera kroz chat panel
        mock_ctrl.view.get_chat_panel.assert_called()

    # ── pretrazi_tarifu ──

    def test_pretrazi_tarifu_sa_nazivom(self, mock_ctrl):
        self._call_execute(mock_ctrl, "pretrazi_tarifu", {"naziv": "čelik"})
        # Proverava da je _pretrazi_tarifu pozvana
        mock_ctrl.view.get_chat_panel().add_activity.assert_called()

    def test_pretrazi_tarifu_bez_naziva(self, mock_ctrl):
        self._call_execute(mock_ctrl, "pretrazi_tarifu", {})
        mock_ctrl.view.get_chat_panel().add_agent_message.assert_called()

    # ── validuj_deklaraciju ──

    def test_validuj_deklaraciju(self, mock_ctrl):
        self._call_execute(mock_ctrl, "validuj_deklaraciju", {})
        mock_ctrl.view.get_chat_panel().add_activity.assert_called()

    # ── prikazi_naimenovanja ──

    def test_prikazi_naimenovanja(self, mock_ctrl):
        self._call_execute(mock_ctrl, "prikazi_naimenovanja", {})
        mock_ctrl.view.get_chat_panel().add_activity.assert_called()

    # ── provjeri_naimenovanja ──

    def test_provjeri_naimenovanja(self, mock_ctrl):
        self._call_execute(mock_ctrl, "provjeri_naimenovanja", {})
        mock_ctrl.view.get_chat_panel().add_activity.assert_called()

    # ── upisi_u_kolonu ──

    def test_upisi_u_kolonu_uspjesno(self, mock_ctrl):
        mock_ctrl.naim_intent_svc._resolve_kolona.return_value = ("tarifni_broj", "faktura")
        self._call_execute(mock_ctrl, "upisi_u_kolonu", {
            "kolona": "tarifni broj",
            "vrijednost": "3304990000"
        })
        mock_ctrl.naim_intent_svc._resolve_kolona.assert_called_once()
        mock_ctrl.naim_intent_svc.execute.assert_called_once_with(
            "tarifni_broj", "3304990000", "faktura"
        )

    def test_upisi_u_kolonu_nepoznata_kolona(self, mock_ctrl):
        mock_ctrl.naim_intent_svc._resolve_kolona.return_value = ("", "faktura")
        self._call_execute(mock_ctrl, "upisi_u_kolonu", {
            "kolona": "nepoznata",
            "vrijednost": "test"
        })
        mock_ctrl.view.get_chat_panel().add_agent_message.assert_called()

    def test_upisi_u_kolonu_bez_vrijednosti(self, mock_ctrl):
        self._call_execute(mock_ctrl, "upisi_u_kolonu", {"kolona": "tarifni broj"})
        mock_ctrl.view.get_chat_panel().add_agent_message.assert_called()

    # ── spoji_naimenovanja ──

    def test_spoji_naimenovanja(self, mock_ctrl):
        self._call_execute(mock_ctrl, "spoji_naimenovanja", {})
        mock_ctrl._predlozi_spajanje_naimenovanja.assert_called_once()

    # ── Nepoznat alat ──

    def test_nepoznat_alat(self, mock_ctrl):
        self._call_execute(mock_ctrl, "nepostojeci_alat", {})
        mock_ctrl.view.get_chat_panel().add_agent_message.assert_called()


# ── ToolDispatcher._dispatch offline test ────────────────────────────

class TestDispatchOffline:
    """Testira _dispatch bez mreže (mockovan API)."""

    def test_dispatch_vraca_error_kad_nema_kljuca(self):
        """Kad nema DeepSeek ključa, vraća DispatchResult sa error-om."""
        from services.agent.chat.tool_dispatcher import ToolDispatcherWorker, DispatchResult

        with patch('gui.tabs.agent.widgets.llm_provider.LLMProvider') as mock_provider:
            instance = mock_provider.return_value
            instance.has_deepseek.return_value = False

            result = ToolDispatcherWorker._dispatch("test poruka")
            assert isinstance(result, DispatchResult)
            assert result.error != ""
            assert result.tool_call is None

    def test_dispatch_vraca_tool_call_kad_api_vrati(self):
        """Simulira uspješan tool call odgovor od DeepSeek API-ja."""
        from services.agent.chat.tool_dispatcher import ToolDispatcherWorker, DispatchResult

        with patch('gui.tabs.agent.widgets.llm_provider.LLMProvider') as mock_prov, \
             patch('openai.OpenAI') as mock_openai:
            instance = mock_prov.return_value
            instance.has_deepseek.return_value = True
            instance.deepseek_key = "sk-test"

            # Mock API response
            mock_msg = MagicMock()
            mock_msg.content = None
            mock_tool_call = MagicMock()
            mock_tool_call.function.name = "pretrazi_tarifu"
            mock_tool_call.function.arguments = '{"naziv": "čelik"}'
            mock_msg.tool_calls = [mock_tool_call]

            mock_choice = MagicMock()
            mock_choice.message = mock_msg

            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]

            mock_client = mock_openai.return_value
            mock_client.chat.completions.create.return_value = mock_resp

            result = ToolDispatcherWorker._dispatch("koji je tarifni broj za čelik?")
            assert isinstance(result, DispatchResult)
            assert result.tool_call is not None
            assert result.tool_call.name == "pretrazi_tarifu"
            assert result.tool_call.arguments == {"naziv": "čelik"}
