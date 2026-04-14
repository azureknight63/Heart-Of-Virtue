"""
HumanNPCLLMMixin — LLM-driven conversational dialogue mixin for human nomad NPCs.

Mixed into NPC classes (e.g. class Mara(HumanNPCLLMMixin, Friend)).
Provides multi-turn conversational dialogue with dialogue history persistence,
loquacity draining, QC pipeline (slang/anachronism filtering, proper noun validation),
and graceful fallback to deterministic dialogue pools when LLM is unavailable.

Attributes expected on the host class (set before or during __init__):
    self.name                str
    self.charisma            int
    self.wisdom              int (used for loquacity recovery calculation)
    self.keywords            list[str] (will have "chat" added if missing)

Optional setup (for story NPCs only):
    self._chat_config_path   str | None (path to character JSON config)

Instance attributes (set by _init_chat_attrs):
    self.loquacity_current   int (current conversation stamina)
    self.loquacity_max       int (max stamina for this NPC)
    self.loquacity_threshold int (minimum to start new conversation)
    self.loquacity_recovery  int (per-beat recovery when not in conversation)
    self._chat_history       list[dict] (in-memory exchange log)
    self._chat_personality   dict | None (for generic nomads)
    self._chat_npc_key       str | None (persistence key)
"""

import importlib.util
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_AI_DIR = Path(__file__).resolve().parent.parent.parent / "ai"
_HUMAN_NPC_DIR = _AI_DIR / "npc" / "human"
_WORLD_FACTS_PATH = _HUMAN_NPC_DIR / "world_facts.json"

# Modern slang / anachronism blocklist (regex pattern)
_SLANG_PATTERN = re.compile(
    r"\b(okay|hey there|yeah|yep|nope|cool|awesome|literally|basically|"
    r"gonna|wanna|gotta|no worries|you know\?|guns?|bombs?|bullets?|internet)\b",
    re.IGNORECASE,
)

# Jean-dialogue guard: reject if NPC text describes Jean speaking
_JEAN_DIALOG_PATTERN = re.compile(r"jean\s+(said|replied|asked|told)\b|jean:\s*[\"']", re.IGNORECASE)

# Capitalized token finder (for invented proper noun scan)
_CAP_TOKEN_PATTERN = re.compile(r"\b([A-Z][A-Za-z\-]{2,})\b")

# Drain amounts keyed by conversation_quality
_LOQUACITY_DRAIN = {"positive": 3, "neutral": 8, "negative": 15, "offensive": 30}

# Jean options fallback pool (rotated to avoid repetition)
_JEAN_FALLBACK_POOL = [
    [
        {"tone": "direct", "text": "What else can you tell me?"},
        {"tone": "guarded", "text": "I'll keep that in mind."},
        {"tone": "open", "text": "That's worth knowing."},
    ],
    [
        {"tone": "direct", "text": "Go on."},
        {"tone": "guarded", "text": "Noted."},
        {"tone": "open", "text": "Tell me more."},
    ],
    [
        {"tone": "direct", "text": "Fair enough."},
        {"tone": "guarded", "text": "I see."},
        {"tone": "open", "text": "I'm listening."},
    ],
]

# Generic nomad fallbacks (selected via hash to ensure determinism)
_GENERIC_FALLBACKS = [
    {
        "given_name": "Ren",
        "voice": "sparse and direct",
        "knowledge": ["river crossings", "camp craft"],
        "attitude_to_strangers": "wary",
        "speech_sample": "River's cold this time of year. Careful at the bend.",
        "loquacity_base": 55,
    },
    {
        "given_name": "Tal",
        "voice": "methodical, speaks in short declaratives",
        "knowledge": ["trade routes", "reading terrain"],
        "attitude_to_strangers": "indifferent",
        "speech_sample": "East road's clear. Not sure about the west.",
        "loquacity_base": 65,
    },
    {
        "given_name": "Sev",
        "voice": "guarded but not hostile",
        "knowledge": ["weather patterns", "foraging"],
        "attitude_to_strangers": "guarded",
        "speech_sample": "Storm's coming in from the north. Two days, maybe three.",
        "loquacity_base": 50,
    },
    {
        "given_name": "Vael",
        "voice": "curious, observant",
        "knowledge": ["people-reading", "the Badlands by reputation"],
        "attitude_to_strangers": "curious",
        "speech_sample": "Jean's not from around here. Most people who look like that aren't.",
        "loquacity_base": 70,
    },
]


class HumanNPCLLMMixin:
    """LLM-driven conversational dialogue mixin for human nomad NPCs."""

    def _init_chat_attrs(self):
        """Initialize all chat-related attributes. Called at end of host __init__."""
        # Config path can be set by subclass before calling this
        self._chat_config_path: Optional[str] = getattr(self, "_chat_config_path", None)

        # Load character config if path provided
        self._chat_char_config: Optional[Dict[str, Any]] = None
        if self._chat_config_path:
            try:
                with open(self._chat_config_path, "r", encoding="utf-8") as f:
                    self._chat_char_config = json.load(f)
            except Exception as e:
                logger.debug(f"Could not load chat config from {self._chat_config_path}: {e}")

        # Load world facts
        self._chat_world_facts: Optional[Dict[str, Any]] = None
        try:
            with open(_WORLD_FACTS_PATH, "r", encoding="utf-8") as f:
                self._chat_world_facts = json.load(f)
        except Exception as e:
            logger.debug(f"Could not load world facts: {e}")
            self._chat_world_facts = {}

        # For generic nomads: generated on first talk
        self._chat_personality: Optional[Dict[str, Any]] = None

        # In-memory exchange history
        self._chat_history: List[Dict[str, Any]] = []

        # Persistence key (lazy-loaded)
        self._chat_npc_key: Optional[str] = None

        # LLM adapter (lazy-loaded)
        self._chat_adapter: Optional[Any] = None

        # Regeneration guard
        self._chat_regen_count: int = 0

        # Fallback rotation index
        self._chat_fallback_idx: int = 0

        # Loquacity system
        self.loquacity_current: int = 0
        self.loquacity_max: int = 0
        self.loquacity_threshold: int = 0
        self.loquacity_recovery: int = 2

        # Add "chat" to keywords if not present
        if not hasattr(self, "keywords"):
            self.keywords = []
        if "chat" not in self.keywords:
            self.keywords.append("chat")

    def _get_adapter(self) -> Optional[Any]:
        """Lazy-load NpcChatLLMAdapter via importlib. Return None on failure."""
        if self._chat_adapter is not None:
            return self._chat_adapter

        try:
            spec = importlib.util.find_spec("ai.llm_client")
            if spec is None:
                # Try direct path import
                path = str(_AI_DIR / "llm_client.py")
                spec = importlib.util.spec_from_file_location("ai_llm_client", path)

            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self._chat_adapter = module.NpcChatLLMAdapter.get_instance()
        except Exception as e:
            logger.debug(f"HumanNPCLLMMixin: could not load adapter: {e}")
            self._chat_adapter = None

        return self._chat_adapter

    def _story(self, player) -> Dict[str, Any]:
        """Get story dict from player.universe, or empty dict."""
        return getattr(getattr(player, "universe", None), "story", None) or {}

    def _get_chapter(self, player) -> str:
        """Get current chapter as string."""
        return str(self._story(player).get("chapter", "1"))

    def _compute_loquacity(self, player):
        """Compute and set loquacity_max, threshold, and recovery. Only on first call."""
        if self.loquacity_max != 0:
            return  # Already computed

        # Base loquacity
        base = (
            (self._chat_char_config or {}).get("loquacity_base")
            or (self._chat_personality or {}).get("loquacity_base")
            or 60
        )

        # NPC charisma bonus
        npc_charisma_bonus = (getattr(self, "charisma", 10) - 10) * 3

        # Reputation modifier
        rep = getattr(player, "reputation", {}).get(self.name, 0)
        story_mod = 20 if rep >= 1 else (-20 if rep <= -1 else 0)

        # Jean's charisma modifier
        jean_stat_mod = (getattr(player, "charisma", 10) - 10) * 2

        # Equipment check
        equipped = getattr(player, "equipped", {})
        equip_names = []
        if isinstance(equipped, dict):
            for v in equipped.values():
                if isinstance(v, dict):
                    equip_names.append(str(v.get("name", "")).lower())
                else:
                    equip_names.append(str(v).lower())
        equip_text = " ".join(equip_names)
        equip_mod = 10 if any(x in equip_text for x in ("crucifix", "religious token", "nomad gear")) else 0

        # Party check (Gorran in allies)
        allies = getattr(player, "allies", [])
        party_mod = 10 if any(getattr(a, "name", "") == "Gorran" for a in allies) else 0

        loquacity_max = max(20, base + npc_charisma_bonus + story_mod + jean_stat_mod + equip_mod + party_mod)

        self.loquacity_max = loquacity_max
        self.loquacity_threshold = max(10, loquacity_max // 5)
        self.loquacity_recovery = max(2, getattr(self, "wisdom", 10) // 8)

        if self.loquacity_current == 0:
            self.loquacity_current = loquacity_max

    def _get_npc_key(self, player) -> str:
        """Get or generate persistence key for this NPC instance."""
        if self._chat_npc_key:
            return self._chat_npc_key

        # Story NPCs use their name
        if self._chat_char_config:
            self._chat_npc_key = self.name
            return self._chat_npc_key

        # Generic nomads use class name + instance count
        hists = getattr(player, "npc_chat_histories", {})
        meta = hists.get("__meta__", {})
        class_name = type(self).__name__
        instance_count = meta.get(class_name, 0)

        self._chat_npc_key = f"{class_name}_{instance_count}"

        # Increment for next generic of same type
        if "__meta__" not in hists:
            hists["__meta__"] = {}
        hists["__meta__"][class_name] = instance_count + 1

        return self._chat_npc_key

    def _load_history_from_persistence(self, player):
        """Load chat history and personality from player persistence."""
        hists = getattr(player, "npc_chat_histories", {})
        key = self._chat_npc_key
        if not key or key not in hists:
            return

        entry = hists[key]
        self._chat_history = entry.get("exchanges", [])
        if "personality" in entry and entry["personality"]:
            self._chat_personality = entry["personality"]

        stored_loquacity = entry.get("loquacity_current", 0)
        if stored_loquacity > 0:
            self.loquacity_current = stored_loquacity

    def _save_exchange_to_persistence(
        self, player, npc_text: str, jean_text: str, game_tick: int, chapter: str
    ):
        """Save exchange to player persistence."""
        hists = getattr(player, "npc_chat_histories", None)
        if hists is None:
            return

        key = self._chat_npc_key
        if key not in hists:
            hists[key] = {
                "personality": None,
                "loquacity_current": self.loquacity_current,
                "loquacity_max": self.loquacity_max,
                "exchanges": [],
                "last_talked_tick": 0,
                "conversation_count": 0,
            }

        entry = hists[key]
        entry["exchanges"].append(
            {"npc": npc_text, "jean": jean_text, "game_tick": game_tick, "chapter": chapter}
        )

        # Keep only last 20 exchanges
        if len(entry["exchanges"]) > 20:
            entry["exchanges"] = entry["exchanges"][-20:]

        entry["loquacity_current"] = self.loquacity_current
        entry["loquacity_max"] = self.loquacity_max
        entry["last_talked_tick"] = game_tick

        # Only increment conversation count on full exchanges (with jean_text)
        if jean_text:
            entry["conversation_count"] = entry.get("conversation_count", 0) + 1

        # Store personality for generics
        if self._chat_personality:
            entry["personality"] = self._chat_personality

    def _build_system_prompt(self, player) -> str:
        """Build system prompt from world facts + character block."""
        blocks = []

        # World facts block
        if self._chat_world_facts:
            geo = ", ".join(self._chat_world_facts.get("geography", []))
            factions = ", ".join(self._chat_world_facts.get("factions_and_peoples", []))
            rules = " ".join(self._chat_world_facts.get("world_rules", []))
            tone = self._chat_world_facts.get("tone_notes", "")

            blocks.append(
                f"WORLD: {self._chat_world_facts.get('world_name', 'Aurelion')}. "
                f"{self._chat_world_facts.get('brief_description', '')}\n"
                f"Places: {geo}.\nPeoples: {factions}.\n{rules}\nTone: {tone}"
            )

        # Character block
        if self._chat_char_config:
            # Story NPC: use system_prompt_snippet
            blocks.append(self._chat_char_config.get("system_prompt_snippet", ""))
        else:
            # Generic NPC: synthesize from personality
            pers = self._chat_personality or {}
            given_name = pers.get("given_name", "Nomad")
            voice = pers.get("voice", "terse")
            knowledge_list = pers.get("knowledge", [])
            knowledge = ", ".join(knowledge_list) if knowledge_list else "survival"

            blocks.append(
                f"You are {given_name}, a nomad. {voice}. "
                f"You know about {knowledge}. You speak in first person. "
                "Keep responses to 1-3 sentences."
            )

        # Jean instruction block
        blocks.append(
            "Jean is he/him. Do not write Jean's dialogue. Do not describe Jean's internal state."
        )

        return "\n\n".join(blocks)

    def _ensure_personality(self, player):
        """For generics: generate personality on first talk, or use fallback."""
        if self._chat_char_config or self._chat_personality:
            return  # Already set (story NPC or already generated)

        adapter = self._get_adapter()
        class_name = type(self).__name__

        if adapter and adapter.enabled:
            self._chat_personality = adapter.generate_personality(class_name)

        # Fallback if LLM unavailable
        if not self._chat_personality:
            key = self._chat_npc_key or self.name
            idx = hash(key) % len(_GENERIC_FALLBACKS)
            self._chat_personality = _GENERIC_FALLBACKS[idx].copy()

    def _jaccard(self, text_a: str, text_b: str) -> float:
        """Compute Jaccard similarity of two texts (word-level tokenization)."""
        set_a = set(text_a.lower().split())
        set_b = set(text_b.lower().split())

        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0

        intersection = len(set_a & set_b)
        union = len(set_a | set_b)

        return intersection / union if union > 0 else 0.0

    def _qc_npc_text(self, text: str, history: List[Dict[str, Any]]) -> Optional[str]:
        """Apply QC pipeline. Return cleaned text or None."""
        # Step 1: Strip and length check
        text = text.strip()
        if not text or len(text) < 10:
            return None

        # Step 2: Truncate at sentence boundary if too long
        if len(text) > 300:
            # Find last sentence boundary before 300
            boundary_pos = -1
            for i in range(299, -1, -1):
                if text[i] in ".!?":
                    boundary_pos = i + 1
                    break

            if boundary_pos > 0:
                text = text[:boundary_pos].strip()
            else:
                text = text[:300].strip()

        # Step 3: Reject if Jean-dialogue pattern found
        if _JEAN_DIALOG_PATTERN.search(text):
            return None

        # Step 4: Invented proper noun scan
        world_nouns = set(
            (self._chat_world_facts or {}).get("allowed_proper_nouns", [])
        )
        world_nouns.update([self.name, "Jean", "Gorran"])

        tokens = _CAP_TOKEN_PATTERN.findall(text)
        for token in tokens:
            if token not in world_nouns:
                # Heuristic: if -ia, -on, -or endings, replace with "that place"
                # Otherwise replace with "they"
                if token.endswith(("ia", "on", "or")):
                    text = re.sub(r"\b" + re.escape(token) + r"\b", "that place", text)
                else:
                    text = re.sub(r"\b" + re.escape(token) + r"\b", "they", text)

        # Step 5: Slang filter
        text = _SLANG_PATTERN.sub("", text).strip()
        if not text or len(text) < 10:
            return None

        # Step 6: Prohibited phrases (story chars only)
        if self._chat_char_config:
            prohibited = self._chat_char_config.get("prohibited_phrases", [])
            for phrase in prohibited:
                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                text = pattern.sub("[...]", text)

        # Step 7: Repetition guard
        for prior in history[-8:]:
            prior_npc = prior.get("npc", "")
            if prior_npc and self._jaccard(text, prior_npc) > 0.7:
                self._chat_regen_count += 1
                if self._chat_regen_count <= 1:
                    return None
                # Else accept with warning
                logger.warning(f"HumanNPCLLMMixin: repetition detected but accepting (count={self._chat_regen_count})")
                break

        # Step 8: Terminal punctuation
        if text and text[-1] not in ".!?":
            text += "."

        # Step 9: Sentence cap (keep first 3 sentences)
        sentences = [s.strip() for s in re.split(r"[.!?]", text) if s.strip()]
        text = ". ".join(sentences[:3])
        if text and text[-1] not in ".!?":
            text += "."

        return text

    def _qc_jean_options(self, options: Any) -> Optional[List[Dict[str, str]]]:
        """QC Jean dialogue options. Return cleaned list or None."""
        if not isinstance(options, list) or len(options) < 3:
            return None

        # Extract and validate first 3 items
        validated = []
        for i, opt in enumerate(options[:3]):
            if not isinstance(opt, dict) or "text" not in opt:
                return None

            text = str(opt.get("text", "")).strip()
            if not (5 <= len(text) <= 120):
                return None

            # No meta-speech
            if re.search(r"\[Option|\bAs Jean\b|I don.t know what to say", text, re.IGNORECASE):
                return None

            tone = str(opt.get("tone", ["direct", "guarded", "open"][i])).lower()
            if tone not in ("direct", "guarded", "open"):
                tone = ["direct", "guarded", "open"][i]

            validated.append({"tone": tone, "text": text})

        # Dedup check
        for i in range(len(validated)):
            for j in range(i + 1, len(validated)):
                if self._jaccard(validated[i]["text"], validated[j]["text"]) > 0.6:
                    return None

        return validated

    def chat_open(self, player) -> Dict[str, Any]:
        """Start conversation. Returns opening line + 3 Jean options."""
        try:
            self._chat_regen_count = 0
            self._compute_loquacity(player)
            npc_key = self._get_npc_key(player)
            self._load_history_from_persistence(player)

            # Loquacity cutoff
            if self.loquacity_current < self.loquacity_threshold:
                brush_off = self._get_brush_off_line()
                return {
                    "success": True,
                    "npc_key": npc_key,
                    "npc_name": self._display_name(),
                    "npc_opening": brush_off,
                    "jean_options": [],
                    "loquacity_current": self.loquacity_current,
                    "loquacity_max": self.loquacity_max,
                    "turn": 0,
                    "llm_available": False,
                    "conversation_ended": True,
                }

            self._ensure_personality(player)
            system = self._build_system_prompt(player)
            adapter = self._get_adapter()
            llm_available = adapter is not None and adapter.enabled

            # Generate NPC opening
            npc_opening = None
            if llm_available:
                for attempt in range(2):
                    result = adapter.generate_npc_turn(
                        system, self._chat_history, is_opening=True
                    )
                    if result and result.get("npc_text"):
                        cleaned = self._qc_npc_text(result["npc_text"], self._chat_history)
                        if cleaned:
                            npc_opening = cleaned
                            break
                        self._chat_regen_count += 1

            if not npc_opening:
                npc_opening = self._get_fallback_npc_line(is_opening=True, player=player)
                llm_available = False

            # Generate Jean options
            jean_options = None
            if llm_available and adapter:
                voice = (self._chat_char_config or {}).get("voice_summary") or (
                    self._chat_personality or {}
                ).get("voice", "")
                raw_opts = adapter.generate_jean_options(
                    self._display_name(), voice, npc_opening, self._chat_history, 0
                )
                if raw_opts:
                    jean_options = self._qc_jean_options(raw_opts)

            if not jean_options:
                jean_options = self._get_fallback_jean_options()

            game_tick = getattr(getattr(player, "universe", None), "game_tick", 0) or 0
            chapter = self._get_chapter(player)
            self._save_exchange_to_persistence(player, npc_opening, "", game_tick, chapter)

            return {
                "success": True,
                "npc_key": npc_key,
                "npc_name": self._display_name(),
                "npc_opening": npc_opening,
                "jean_options": jean_options,
                "loquacity_current": self.loquacity_current,
                "loquacity_max": self.loquacity_max,
                "turn": 0,
                "llm_available": llm_available,
                "conversation_ended": False,
            }
        except Exception as e:
            logger.error(f"HumanNPCLLMMixin.chat_open error: {e}")
            return {"success": False, "error": str(e)}

    def chat_respond(
        self, player, jean_text: str, jean_tone: str
    ) -> Dict[str, Any]:
        """Process Jean's response. Returns NPC reply + 3 new Jean options."""
        try:
            self._compute_loquacity(player)
            npc_key = self._get_npc_key(player)
            self._load_history_from_persistence(player)

            # Update last history entry with jean_text, or append new
            if self._chat_history and not self._chat_history[-1].get("jean"):
                self._chat_history[-1]["jean"] = jean_text
            else:
                game_tick = getattr(getattr(player, "universe", None), "game_tick", 0) or 0
                chapter = self._get_chapter(player)
                self._chat_history.append(
                    {"npc": "", "jean": jean_text, "game_tick": game_tick, "chapter": chapter}
                )

            self._ensure_personality(player)
            system = self._build_system_prompt(player)
            adapter = self._get_adapter()
            llm_available = adapter is not None and adapter.enabled

            # Generate NPC response
            npc_response = None
            conversation_quality = "neutral"

            if llm_available:
                for attempt in range(2):
                    result = adapter.generate_npc_turn(
                        system,
                        self._chat_history,
                        is_opening=False,
                        jean_text=jean_text,
                    )
                    if result and result.get("npc_text"):
                        cleaned = self._qc_npc_text(result["npc_text"], self._chat_history)
                        if cleaned:
                            npc_response = cleaned
                            conversation_quality = result.get("conversation_quality", "neutral")
                            break
                        self._chat_regen_count += 1

            if not npc_response:
                npc_response = self._get_fallback_npc_line(is_opening=False, player=player)
                llm_available = False

            # Drain loquacity
            drain = _LOQUACITY_DRAIN.get(conversation_quality, 8)
            self.loquacity_current = max(0, self.loquacity_current - drain)

            # Persist exchange
            game_tick = getattr(getattr(player, "universe", None), "game_tick", 0) or 0
            chapter = self._get_chapter(player)
            if self._chat_history and not self._chat_history[-1].get("npc"):
                self._chat_history[-1]["npc"] = npc_response
            else:
                self._save_exchange_to_persistence(
                    player, npc_response, jean_text, game_tick, chapter
                )
            self._save_exchange_to_persistence(player, npc_response, jean_text, game_tick, chapter)

            # Check conversation end
            conversation_ended = (
                self.loquacity_current < self.loquacity_threshold
            )

            # Generate Jean options or return closing
            jean_options = []
            if not conversation_ended:
                if llm_available and adapter:
                    voice = (self._chat_char_config or {}).get("voice_summary") or (
                        self._chat_personality or {}
                    ).get("voice", "")
                    turn_number = len(self._chat_history)
                    raw_opts = adapter.generate_jean_options(
                        self._display_name(),
                        voice,
                        npc_response,
                        self._chat_history,
                        turn_number,
                    )
                    if raw_opts:
                        jean_options = self._qc_jean_options(raw_opts) or []

                if not jean_options:
                    jean_options = self._get_fallback_jean_options()

            return {
                "success": True,
                "npc_key": npc_key,
                "npc_response": npc_response,
                "jean_options": jean_options,
                "loquacity_current": self.loquacity_current,
                "loquacity_max": self.loquacity_max,
                "turn": len(self._chat_history),
                "llm_available": llm_available,
                "conversation_ended": conversation_ended,
            }
        except Exception as e:
            logger.error(f"HumanNPCLLMMixin.chat_respond error: {e}")
            return {"success": False, "error": str(e)}

    def loquacity_tick(self):
        """Recover loquacity each game beat (called outside active conversation)."""
        self.loquacity_current = min(
            self.loquacity_max,
            self.loquacity_current + self.loquacity_recovery,
        )

    def _display_name(self) -> str:
        """Return display name for this NPC."""
        if self._chat_char_config:
            return self.name
        # Generic: use generated name if available
        if self._chat_personality and "given_name" in self._chat_personality:
            return self._chat_personality["given_name"]
        return self.name

    def _get_brush_off_line(self) -> str:
        """Get brush-off when loquacity exhausted."""
        if self._chat_char_config:
            lines = self._chat_char_config.get("closing_lines_when_exhausted", [])
            if lines:
                return lines[0]
        # Generic fallback
        idx = hash(self.name) % 3
        fallbacks = [
            "They're not in the mood to talk.",
            "A brief shake of the head.",
            "Not now.",
        ]
        return fallbacks[idx]

    def _get_fallback_npc_line(
        self, is_opening: bool, player
    ) -> str:
        """Get fallback NPC line (no LLM)."""
        if self._chat_char_config:
            chapter = self._get_chapter(player)
            if is_opening:
                starters = self._chat_char_config.get(
                    "conversation_starters_by_chapter", {}
                ).get(chapter, [])
                if starters:
                    return starters[0]
            else:
                closing = self._chat_char_config.get("closing_lines_when_exhausted", [])
                if closing:
                    return closing[0]
        else:
            # Generic
            if self._chat_personality and "speech_sample" in self._chat_personality:
                return self._chat_personality["speech_sample"]

        return "Nothing to say right now."

    def _get_fallback_jean_options(self) -> List[Dict[str, str]]:
        """Return fallback Jean options, cycling through pool."""
        pool = _JEAN_FALLBACK_POOL[self._chat_fallback_idx % len(_JEAN_FALLBACK_POOL)]
        self._chat_fallback_idx += 1
        return pool
