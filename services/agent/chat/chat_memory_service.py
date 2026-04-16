"""
Chat Memory Service - Pamćenje konteksta chat sesije.

Čuva chat istoriju tokom sesije i omogućava AI-u da "pamti"
šta je korisnik već pitao i šta je agent odgovorio.

Usage:
    memory = ChatMemoryService(project="asycuda_pro")
    memory.add_message("user", "Kako da uvezem fakturu?")
    memory.add_message("assistant", "Koristi Agent tab...")
    context = memory.get_context()  # Za AI
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any


class ChatMessage:
    """Pojedinačna chat poruka."""
    
    def __init__(self, role: str, content: str, timestamp: str = None):
        self.role = role  # "user" | "assistant" | "system"
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp")
        )


class ChatMemoryService:
    """
    Servis za pamćenje chat konteksta.
    
    Čuva poruke u memoriji tokom sesije i omogućava:
    - Dodavanje poruka
    - Dobijanje konteksta za AI
    - Pretraživanje istorije
    - Čuvanje/ucitavanje sesije
    """
    
    # Max poruka u kontekstu (za AI limit)
    MAX_CONTEXT_MESSAGES = 20
    
    # Max ukupnih poruka u istoriji
    MAX_HISTORY_MESSAGES = 100
    
    def __init__(self, project: str = "asycuda_pro"):
        self.project = project
        self.messages: List[ChatMessage] = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start = datetime.now()
        
        # Sistem prompt za AI
        self._system_prompt = self._get_base_system_prompt()
    
    def _get_base_system_prompt(self) -> str:
        """Bazni sistem prompt za agenta."""
        return """Ti si ASYCUDA Pro asistent - carinska aplikacija za deklaracije.

Tvoje funkcije:
- Pomoć pri importu faktura (PDF, Excel)
- Predlaganje tarifnih brojeva
- Automatizacija carinskih postupaka
- XML export deklaracija

Odgovaraj na srpskom, budi kratak i precizan.
Ako ne znaš odgovor, reci "Ne znam" umjesto da izmišljaš.
"""
    
    def add_message(self, role: str, content: str) -> ChatMessage:
        """
        Dodaj poruku u chat istoriju.
        
        Args:
            role: "user" | "assistant" | "system"
            content: Tekst poruke
            
        Returns:
            Kreirana ChatMessage
        """
        # Očisti HTML tagove iz content-a za bolji kontekst
        clean_content = self._strip_html(content)
        
        message = ChatMessage(role, clean_content)
        self.messages.append(message)
        
        # Ograniči veličinu istorije
        if len(self.messages) > self.MAX_HISTORY_MESSAGES:
            self.messages = self.messages[-self.MAX_HISTORY_MESSAGES:]
        
        return message
    
    def add_user_message(self, content: str) -> ChatMessage:
        """Dodaj korisničku poruku."""
        return self.add_message("user", content)
    
    def add_assistant_message(self, content: str) -> ChatMessage:
        """Dodaj AI asistent poruku."""
        return self.add_message("assistant", content)
    
    def get_context(self, max_messages: int = None) -> List[Dict[str, str]]:
        """
        Dobij kontekst za AI (samo zadnje poruke).
        
        Args:
            max_messages: Koliko poruka uključiti (default: MAX_CONTEXT_MESSAGES)
            
        Returns:
            Lista dict-ova: [{"role": "...", "content": "..."}]
        """
        if max_messages is None:
            max_messages = self.MAX_CONTEXT_MESSAGES
        
        # Uzmi zadnje poruke
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        
        return [msg.to_dict() for msg in recent]
    
    def get_full_history(self) -> List[Dict[str, str]]:
        """Dobij kompletnu chat istoriju."""
        return [msg.to_dict() for msg in self.messages]
    
    def search_history(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Pretraži chat istoriju po keyword-ima.
        
        Args:
            query: Query string
            limit: Max rezultata
            
        Returns:
            Lista poruka sa match-eva
        """
        query_lower = query.lower()
        results = []
        
        # Tokenize query
        query_tokens = set(re.findall(r'\w+', query_lower))
        
        for msg in reversed(self.messages):  # Najnovije prvo
            content_lower = msg.content.lower()
            
            # Jednostavno preklapanje riječi
            content_tokens = set(re.findall(r'\w+', content_lower))
            overlap = query_tokens & content_tokens
            
            if overlap:
                score = len(overlap) / max(len(query_tokens), 1)
                results.append({
                    "message": msg.to_dict(),
                    "score": score,
                    "matched_tokens": list(overlap)
                })
                
                if len(results) >= limit:
                    break
        
        return results
    
    def get_conversation_summary(self) -> str:
        """
        Dobij sažetak konverzacije (prvih par poruka).
        
        Returns:
            String sažetka
        """
        if not self.messages:
            return "(Nema poruka)"
        
        total = len(self.messages)
        user_count = sum(1 for m in self.messages if m.role == "user")
        assistant_count = sum(1 for m in self.messages if m.role == "assistant")
        
        # Prva korisnička poruka
        first_user = next((m.content[:100] for m in self.messages if m.role == "user"), "")
        
        return (
            f"Sesija #{self.session_id}\n"
            f"Poruka: {total} ({user_count} korisnik, {assistant_count} asistent)\n"
            f"Tema: {first_user}..."
        )
    
    def clear(self):
        """Očisti chat istoriju."""
        self.messages.clear()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def export_session(self) -> Dict[str, Any]:
        """
        Eksportuj sesiju za čuvanje.
        
        Returns:
            Dict sa kompletnom sesijom
        """
        return {
            "session_id": self.session_id,
            "project": self.project,
            "start_time": self.session_start.isoformat(),
            "message_count": len(self.messages),
            "messages": self.get_full_history()
        }
    
    def import_session(self, data: Dict[str, Any]):
        """
        Uvezi prethodnu sesiju.
        
        Args:
            data: Dict iz export_session()
        """
        self.session_id = data.get("session_id", self.session_id)
        self.messages = [
            ChatMessage.from_dict(m) for m in data.get("messages", [])
        ]
    
    # === Pomocne metode ===
    
    @staticmethod
    def _strip_html(text: str) -> str:
        """Ukloni HTML tagove iz teksta."""
        if not text:
            return ""
        # Ukloni common HTML tagove
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        # Čuvaj nove redove
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()
    
    def __len__(self) -> int:
        return len(self.messages)
    
    def __repr__(self) -> str:
        return f"<ChatMemoryService: {len(self.messages)} poruka, sesija {self.session_id}>"
