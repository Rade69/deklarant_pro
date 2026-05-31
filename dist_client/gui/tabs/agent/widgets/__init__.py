"""
Agent Widgets.

Public API:
    >>> from gui.tabs.agent.widgets import (
    ...     HeaderBar, UploadArea, DocumentPanel, FileTable,
    ...     ResultsViewer, ChatPanel, LLMProvider, ProcessingWorker,
    ...     ChatWorker, TariffLLMWorker,
    ... )
"""

from gui.tabs.agent.widgets.header_bar import HeaderBar
from gui.tabs.agent.widgets.upload_area import UploadArea
from gui.tabs.agent.widgets.document_panel import DocumentPanel
from gui.tabs.agent.widgets.file_table import FileTable
from gui.tabs.agent.widgets.results_viewer import ResultsViewer
from gui.tabs.agent.widgets.chat_panel import ChatPanel
from gui.tabs.agent.widgets.llm_provider import LLMProvider
from gui.tabs.agent.widgets.processing_worker import ProcessingWorker
from gui.tabs.agent.widgets.chat_worker import ChatWorker
from gui.tabs.agent.widgets.tariff_llm_worker import TariffLLMWorker

__all__ = [
    "HeaderBar",
    "UploadArea",
    "DocumentPanel",
    "FileTable",
    "ResultsViewer",
    "ChatPanel",
    "LLMProvider",
    "ProcessingWorker",
    "ChatWorker",
    "TariffLLMWorker",
]
