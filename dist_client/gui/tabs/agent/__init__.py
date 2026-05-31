"""
Agent Tab — pregled i validacija naimenovanja, LLM chat, tarifni prijedlozi.

Public API:
    >>> from gui.tabs.agent import AgentController, AgentView
    >>> from gui.tabs.agent import FileItem, TariffProposal, PendingAction
"""

from gui.tabs.agent.agent_view import AgentView
from gui.tabs.agent.agent_controller import AgentController
from gui.tabs.agent.models.file_item import FileItem
from gui.tabs.agent.agent_actions import TariffProposal, NaimenovanjaSpajanje, PendingAction

__all__ = [
    "AgentView",
    "AgentController",
    "FileItem",
    "TariffProposal",
    "NaimenovanjaSpajanje",
    "PendingAction",
]
