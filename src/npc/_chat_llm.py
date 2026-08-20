"""
ConversationalNPCMixin — LLM-driven conversational dialogue mixin for speaking NPCs.

Mixed into NPC classes (e.g. class Mara(ConversationalNPCMixin, Friend)).
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

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ._llm import _load_llm_client_module
from src.narration import narrate

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
_JEAN_DIALOG_PATTERN = re.compile(
    r"jean\s+(said|replied|asked|told)\b|jean:\s*[\"']", re.IGNORECASE
)

# Capitalized token finder (for invented proper noun scan)
_CAP_TOKEN_PATTERN = re.compile(r"\b([A-Z][A-Za-z\-]{2,})\b")

# Common capitalized words that are NOT invented proper nouns. Sentence-initial
# words are skipped positionally; this set catches legitimate capitalized words
# that can appear mid-sentence (pronouns, connectives, setting/religious terms)
# so the invented-noun scrubber never mangles ordinary English.
_COMMON_CAP_WORDS = frozenset(
    w.lower()
    for w in (
        "The", "This", "That", "These", "Those", "There", "Then", "Here",
        "What", "When", "Where", "Why", "Who", "How", "But", "And", "Not",
        "Now", "Yes", "Well", "Come", "Look", "Listen", "Maybe", "Perhaps",
        "Nothing", "Something", "Someone", "Anyone", "Everyone", "Nobody",
        "He", "She", "His", "Her", "Him", "They", "Them", "Their", "You",
        "Your", "We", "Our", "Its", "God", "Lord", "Heaven", "Hell", "Father",
        "North", "South", "East", "West", "River", "Sun", "Moon", "Storm",
    )
)

# Minimum length for NPC dialogue text to be treated as real content rather
# than empty/near-empty noise. Several NPCs are authored with terse,
# economical voices (Mara: "Says half of what she means") and can
# legitimately reply with "No." or "I see." — a flat 10-character floor
# silently rejected those in-character replies on every single turn, forcing
# unnecessary retries/fallback for exactly the NPCs whose voice most called
# for short answers. This only needs to catch genuinely empty/near-empty
# noise; _has_real_npc_text's alphanumeric check (below) does the actual
# garbage filtering (e.g. "..." or "-").
_MIN_NPC_TEXT_LEN = 2

_HAS_ALNUM_PATTERN = re.compile(r"[A-Za-z0-9]")


def _has_real_npc_text(text: str) -> bool:
    """True if text is long enough and has actual word content (not just
    punctuation/whitespace noise like "..." or "-")."""
    return len(text) >= _MIN_NPC_TEXT_LEN and bool(_HAS_ALNUM_PATTERN.search(text))


# Fallback drain amounts keyed by conversation_quality — used only when the LLM
# does not supply an explicit signed loquacity_delta (legacy adapter / fallback).
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


class ConversationalNPCMixin:
    """LLM-driven conversational dialogue mixin for speaking NPCs."""

    # Class-level caches: files are read once per process, not once per NPC instance.
    _world_facts_cache: Optional[Dict[str, Any]] = None
    _char_config_cache: Dict[str, Any] = {}

    def _init_chat_attrs(self):
        """Initialize all chat-related attributes. Called at end of host __init__."""
        # Config path can be set by subclass before calling this
        self._chat_config_path: Optional[str] = getattr(self, "_chat_config_path", None)

        # Load character config if path provided (class-level cache)
        self._chat_char_config: Optional[Dict[str, Any]] = None
        if self._chat_config_path:
            if self._chat_config_path not in ConversationalNPCMixin._char_config_cache:
                try:
                    with open(self._chat_config_path, "r", encoding="utf-8") as f:
                        ConversationalNPCMixin._char_config_cache[self._chat_config_path] = (
                            json.load(f)
                        )
                except Exception as e:
                    logger.debug(
                        f"Could not load chat config from {self._chat_config_path}: {e}"
                    )
                    ConversationalNPCMixin._char_config_cache[self._chat_config_path] = None
            self._chat_char_config = ConversationalNPCMixin._char_config_cache[
                self._chat_config_path
            ]

        # Load world facts (class-level cache)
        if ConversationalNPCMixin._world_facts_cache is None:
            try:
                with open(_WORLD_FACTS_PATH, "r", encoding="utf-8") as f:
                    ConversationalNPCMixin._world_facts_cache = json.load(f)
            except Exception as e:
                logger.debug(f"Could not load world facts: {e}")
                ConversationalNPCMixin._world_facts_cache = {}
        self._chat_world_facts: Optional[Dict[str, Any]] = (
            ConversationalNPCMixin._world_facts_cache
        )

        # For generic nomads: generated on first talk
        self._chat_personality: Optional[Dict[str, Any]] = None

        # In-memory exchange history
        self._chat_history: List[Dict[str, Any]] = []

        # Persistence key (lazy-loaded)
        self._chat_npc_key: Optional[str] = None

        # LLM adapter (lazy-loaded)
        self._chat_adapter: Optional[Any] = None

        # Fallback rotation index (Jean's options pool)
        self._chat_fallback_idx: int = 0

        # Fallback rotation index (NPC line pool — separate counter so the two
        # rotations don't lock-step and repeat in tandem)
        self._chat_npc_fallback_idx: int = 0

        # Pre-compile prohibited phrase regexes for story NPCs
        self._prohibited_patterns: List[Any] = []
        if self._chat_char_config:
            self._prohibited_patterns = [
                re.compile(re.escape(phrase), re.IGNORECASE)
                for phrase in self._chat_char_config.get("prohibited_phrases", [])
            ]

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

    # Sentinel distinguishing "load failed" from "not yet attempted"
    _ADAPTER_FAILED = object()

    def _get_adapter(self) -> Optional[Any]:
        """Lazy-load NpcChatLLMAdapter via importlib. Return None on failure."""
        if self._chat_adapter is self._ADAPTER_FAILED:
            return None
        if self._chat_adapter is not None:
            return self._chat_adapter

        try:
            # Load through the shared loader so this mixin, the Mynx mixin, and
            # ai.combat_strategist all share ONE ai.llm_client module object
            # registered in sys.modules (issue #380) — the adapter's singleton
            # state is no longer split across mutually-unaware module copies.
            module = _load_llm_client_module(_AI_DIR / "llm_client.py")
            if module is not None:
                self._chat_adapter = module.NpcChatLLMAdapter.get_instance()
            else:
                self._chat_adapter = self._ADAPTER_FAILED
        except Exception as e:
            logger.debug(f"ConversationalNPCMixin: could not load adapter: {e}")
            self._chat_adapter = self._ADAPTER_FAILED

        return (
            self._chat_adapter
            if self._chat_adapter is not self._ADAPTER_FAILED
            else None
        )

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
        equip_mod = (
            10
            if any(
                x in equip_text for x in ("crucifix", "religious token", "nomad gear")
            )
            else 0
        )

        # Party check (Gorran in allies)
        allies = getattr(player, "allies", [])
        party_mod = 10 if any(getattr(a, "name", "") == "Gorran" for a in allies) else 0

        loquacity_max = max(
            20,
            base
            + npc_charisma_bonus
            + story_mod
            + jean_stat_mod
            + equip_mod
            + party_mod,
        )

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

        # Generic nomads use class name + instance count. player.npc_chat_histories
        # doesn't exist on a fresh Player (same gotcha as player.reputation —
        # see CLAUDE.md); initialize it in place so the counter below actually
        # persists instead of being written to a throwaway dict every call.
        if getattr(player, "npc_chat_histories", None) is None:
            player.npc_chat_histories = {}
        hists = player.npc_chat_histories
        meta = hists.setdefault("__meta__", {})
        class_name = type(self).__name__
        instance_count = meta.get(class_name, 0)

        self._chat_npc_key = f"{class_name}_{instance_count}"
        meta[class_name] = instance_count + 1

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

        # Use None (absent) rather than 0 as the "never persisted" sentinel —
        # a persisted 0 (patience exhausted) must be restored as 0, not
        # confused with "no stored value yet" and reset back to full.
        stored_loquacity = entry.get("loquacity_current")
        if stored_loquacity is not None:
            self.loquacity_current = stored_loquacity

    def _save_exchange_to_persistence(
        self, player, npc_text: str, jean_text: str, game_tick: int, chapter: str
    ):
        """Save exchange to player persistence.

        player.npc_chat_histories doesn't exist on a fresh Player instance
        (same gotcha as player.reputation — see CLAUDE.md); a real Player
        (as opposed to the MinimalPlayer API fallback, which does set this in
        __init__) previously hit this every single call and silently
        no-opped, so no chat history, loquacity, or personality ever
        persisted, and even the opening line was invisible to
        self._chat_history on the very next turn.
        """
        # None covers both "attribute never set" and "explicitly set to
        # None" defensively.
        if getattr(player, "npc_chat_histories", None) is None:
            player.npc_chat_histories = {}
        hists = player.npc_chat_histories

        key = self._chat_npc_key
        if key not in hists:
            hists[key] = {
                "personality": None,
                "loquacity_current": self.loquacity_current,
                "loquacity_max": self.loquacity_max,
                "loquacity_recovery": getattr(self, "loquacity_recovery", 2),
                "exchanges": [],
                "last_talked_tick": 0,
                "conversation_count": 0,
            }

        entry = hists[key]
        entry["exchanges"].append(
            {
                "npc": npc_text,
                "jean": jean_text,
                "game_tick": game_tick,
                "chapter": chapter,
            }
        )

        # Keep only last 20 exchanges
        if len(entry["exchanges"]) > 20:
            entry["exchanges"] = entry["exchanges"][-20:]

        entry["loquacity_current"] = self.loquacity_current
        entry["loquacity_max"] = self.loquacity_max
        entry["loquacity_recovery"] = getattr(self, "loquacity_recovery", 2)
        entry["last_talked_tick"] = game_tick

        # Only increment conversation count on full exchanges (with jean_text)
        if jean_text:
            entry["conversation_count"] = entry.get("conversation_count", 0) + 1

        # Store personality for generics
        if self._chat_personality:
            entry["personality"] = self._chat_personality

    def _bump_conversation_count(self, player) -> None:
        """Increment conversation_count for a completed respond round.

        chat_respond persists its new row with jean_text="" (see the call
        site) so the row shape matches chat_open's and next round's history
        fill-in works correctly, which means _save_exchange_to_persistence's
        own jean_text-truthy increment never fires for either caller anymore.
        This does the increment explicitly instead, right after a call that
        is guaranteed to have already created the persisted entry.
        """
        hists = getattr(player, "npc_chat_histories", None)
        key = self._chat_npc_key
        if hists is not None and key in hists:
            hists[key]["conversation_count"] = hists[key].get("conversation_count", 0) + 1

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
            # Story NPC: system_prompt_snippet plus the richer config fields
            # (role/knowledge/personality) that ground the model in-character.
            cfg = self._chat_char_config
            snippet = cfg.get("system_prompt_snippet", "")
            extras = []
            role = cfg.get("role")
            if role:
                extras.append(f"Role: {role}.")
            knowledge = cfg.get("knowledge_scope") or []
            if knowledge:
                extras.append(
                    "You can speak to: " + "; ".join(knowledge) + "."
                )
            notes = cfg.get("personality_notes") or []
            if notes:
                extras.append("About you: " + " ".join(notes))
            char_block = snippet
            if extras:
                char_block = (snippet + "\n" + "\n".join(extras)).strip()
            blocks.append(char_block)
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

        # Combat self-knowledge block (progressing allies only) — the chat is
        # the sole surface for ally growth (no UI elements by design), so the
        # NPC must be able to speak about its own techniques and experience.
        combat_block = self._build_combat_knowledge_block()
        if combat_block:
            blocks.append(combat_block)

        # Jean instruction block + spoiler guard (governs what the NPC — not
        # Jean — is allowed to reference)
        chapter = self._get_chapter(player)
        blocks.append(
            "Jean is he/him. Do not write Jean's dialogue. Do not describe Jean's "
            "internal state.\n"
            f"It is currently chapter {chapter}. Only reference things your character "
            "would plausibly know by now. Never reveal or hint at events, places, "
            "people, or revelations from later in the story."
        )

        # Jean's own knowledge boundary — governs Jean's dialogue OPTIONS,
        # generated in the same call as the NPC's line.
        blocks.append(self._build_jean_context_block(player, chapter))

        return "\n\n".join(blocks)

    def _build_jean_context_block(self, player, chapter: str) -> str:
        """Describe what Jean himself has actually experienced so far.

        Gates Jean's generated dialogue OPTIONS (as opposed to the NPC's own
        chapter guard above, which gates the NPC's line). Without an explicit
        anchor for what Jean personally knows, generated options default to
        generic small talk or, worse, reference events Jean hasn't lived
        through yet. Built from the same story-flag dict the rest of the
        engine reads (``player.universe.story``), so it tracks real narrative
        progress instead of needing separate authoring per NPC.
        """
        story = self._story(player)
        experienced: List[str] = []

        gorran_stage = str(story.get("gorran_language_stage", "0"))
        if gorran_stage != "0":
            experienced.append(
                "Gorran, his Golemite companion, has begun communicating in "
                "words rather than only gesture."
            )

        known = (
            " ".join(experienced)
            if experienced
            else "Nothing unusual beyond ordinary travel and the people he has directly met."
        )
        return (
            f"JEAN'S KNOWN CONTEXT (chapter {chapter}): Jean only knows what he "
            f"has personally witnessed. {known} When generating Jean's dialogue "
            "OPTIONS, never let him reference people, places, events, or "
            "revelations beyond this context, the WORLD facts above, and this "
            "conversation's history — no foreshadowing, no spoilers, nothing "
            "only the NPC or narrator would know."
        )

    def _build_combat_knowledge_block(self) -> str:
        """Describe this ally's combat experience and techniques for the system prompt.

        Empty string for NPCs without ally progression (no growth_profile) —
        generic nomads and non-combat NPCs get no combat block.
        """
        if not getattr(self, "growth_profile", None):
            return ""
        level = int(getattr(self, "level", 1) or 1)
        if level < 3:
            tier = "a capable fighter, still early in the journey"
        elif level < 7:
            tier = "a seasoned fighter, noticeably hardened by recent battles"
        elif level < 13:
            tier = "a veteran of many battles at Jean's side"
        else:
            tier = "a master combatant, honed by long campaigning with Jean"
        techniques = []
        for m in getattr(self, "known_moves", []):
            name = getattr(m, "name", "")
            desc = getattr(m, "description", "")
            # Internal AI actions (NpcAttack/NpcRest/NpcIdle/GorranClub, ...)
            # all ship empty descriptions — a described move is by contract a
            # nameable technique, so new internal moves stay hidden without
            # maintaining a name list here.
            if not name or not desc:
                continue
            techniques.append(f"{name} ({desc})")
        technique_text = "; ".join(techniques) if techniques else "none beyond basic fighting"
        return (
            f"COMBAT SELF-KNOWLEDGE: You fight alongside Jean and you are {tier}. "
            f"Techniques you have mastered: {technique_text}. "
            "If Jean asks about your combat abilities, how you have grown, or your "
            "techniques, answer naturally from this list in your own voice. Never "
            "use game terms like 'level', 'experience points', or 'stats' — speak "
            "of your craft the way a fighter would."
        )

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
        # Step 1: Strip and garbage check (see _has_real_npc_text/_MIN_NPC_TEXT_LEN)
        text = text.strip()
        if not _has_real_npc_text(text):
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

        def _is_sentence_initial(match_start: int) -> bool:
            """True if the token begins a sentence (start of text or after . ! ?)."""
            j = match_start - 1
            while j >= 0 and text[j].isspace():
                j -= 1
            return j < 0 or text[j] in ".!?\"'"

        # Collect invented-noun replacements first so positions stay valid while
        # scanning. Skip world-allowed nouns, common English words, and any token
        # that merely starts a sentence (ordinary capitalization, not a proper noun).
        replacements: Dict[str, str] = {}
        for match in _CAP_TOKEN_PATTERN.finditer(text):
            token = match.group(1)
            if token in world_nouns or token in replacements:
                continue
            if token.lower() in _COMMON_CAP_WORDS:
                continue
            if _is_sentence_initial(match.start()):
                continue
            # Heuristic: -ia, -on, -or endings read as places; else a person/group.
            replacements[token] = (
                "that place" if token.endswith(("ia", "on", "or")) else "they"
            )
        for token, repl in replacements.items():
            text = re.sub(r"\b" + re.escape(token) + r"\b", repl, text)

        # Step 5: Slang filter
        text = _SLANG_PATTERN.sub("", text).strip()
        if not _has_real_npc_text(text):
            return None

        # Step 6: Prohibited phrases (story chars only, patterns pre-compiled in _init_chat_attrs)
        for pattern in self._prohibited_patterns:
            text = pattern.sub("[...]", text)

        # Step 7: Repetition guard — caller's retry loop handles the second attempt
        for prior in history[-8:]:
            prior_npc = prior.get("npc", "")
            if prior_npc and self._jaccard(text, prior_npc) > 0.7:
                return None

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
            if re.search(
                r"\[Option|\bAs Jean\b|I don.t know what to say", text, re.IGNORECASE
            ):
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

    def _generate_turn(
        self, adapter, system: str, is_opening: bool, jean_text: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Dispatch one raw NPC turn to the adapter.

        Prefers the combined ``generate_turn`` (NPC reply + Jean options in one
        call — the round-latency budget depends on this), and falls back to the
        legacy two-method adapter interface for backwards compatibility.

        Returns a normalized dict with keys npc_text, npc_flavor,
        conversation_quality, reputation_delta, loquacity_delta (None if the
        adapter did not supply one), and raw_options (the combined call's
        options list, or None when the adapter produces options via a separate
        call). Returns None on failure.
        """
        if hasattr(adapter, "generate_turn"):
            if is_opening:
                res = adapter.generate_turn(system, self._chat_history, is_opening=True)
            else:
                res = adapter.generate_turn(
                    system, self._chat_history, is_opening=False, jean_text=jean_text
                )
            if not res or not res.get("npc_text"):
                return None
            return {
                "npc_text": res.get("npc_text"),
                "npc_flavor": res.get("npc_flavor", "") or "",
                "conversation_quality": res.get("conversation_quality", "neutral"),
                "reputation_delta": res.get("reputation_delta", 0),
                "loquacity_delta": res.get("loquacity_delta"),
                "raw_options": res.get("jean_options"),
            }

        # Legacy two-call adapter (kept for compatibility with older adapters).
        if is_opening:
            res = adapter.generate_npc_turn(system, self._chat_history, is_opening=True)
        else:
            res = adapter.generate_npc_turn(
                system, self._chat_history, is_opening=False, jean_text=jean_text
            )
        if not res or not res.get("npc_text"):
            return None
        return {
            "npc_text": res.get("npc_text"),
            "npc_flavor": res.get("npc_flavor", "") or "",
            "conversation_quality": res.get("conversation_quality", "neutral"),
            "reputation_delta": res.get("reputation_delta", 0),
            "loquacity_delta": res.get("loquacity_delta"),
            "raw_options": None,
        }

    def _run_npc_turn(
        self, adapter, system: str, llm_available: bool, is_opening: bool, jean_text
    ) -> Optional[Dict[str, Any]]:
        """Produce a QC'd NPC turn, or None if the caller should fall back.

        Allows up to two attempts regardless of adapter shape. A single QC
        rejection (most commonly the repetition guard in ``_qc_npc_text``)
        used to drop the combined single-call path straight to the static
        deterministic fallback line, which is what made NPCs appear to repeat
        themselves verbatim turn after turn. A second attempt costs one extra
        round trip only on the QC-failure path — successful calls are still a
        single round trip — and is worth it to avoid the repeated-fallback
        experience.
        """
        if not llm_available or adapter is None:
            return None
        max_attempts = 2
        for _ in range(max_attempts):
            turn = self._generate_turn(adapter, system, is_opening, jean_text)
            if turn and turn.get("npc_text"):
                cleaned = self._qc_npc_text(turn["npc_text"], self._chat_history)
                if cleaned:
                    turn["npc_text"] = cleaned
                    return turn
        return None

    def _resolve_jean_options(
        self, turn: Optional[Dict[str, Any]], adapter, npc_line: str, turn_number: int
    ) -> List[Dict[str, str]]:
        """Return three QC'd Jean options.

        Uses options already returned by a combined turn; otherwise requests them
        from a legacy adapter; otherwise falls back to the deterministic pool.
        Never makes a second LLM call on the combined path (protects the budget).
        """
        combined = adapter is not None and hasattr(adapter, "generate_turn")
        if turn is not None and combined:
            options = self._qc_jean_options(turn.get("raw_options") or [])
            return options or self._get_fallback_jean_options()
        if turn is not None and adapter is not None:
            voice = (self._chat_char_config or {}).get("voice_summary") or (
                self._chat_personality or {}
            ).get("voice", "")
            raw = adapter.generate_jean_options(
                self._display_name(), voice, npc_line, self._chat_history, turn_number
            )
            if raw:
                options = self._qc_jean_options(raw)
                if options:
                    return options
        return self._get_fallback_jean_options()

    def chat(self, player):
        """Interact-system entry point for the 'chat' keyword.

        When the frontend's LLM-chat routing is active (llm_chat_enabled), the
        'chat' and 'talk' keywords are intercepted client-side and open the
        NpcChatPanel via the /api/npc-chat endpoints — this method is never
        called.  If those checks are ever bypassed (disabled env, older
        frontend), fall back to the NPC's static talk dialogue so the player
        still gets a response instead of an AttributeError.
        """
        if hasattr(self, "talk"):
            self.talk(player)
        else:
            narrate(self._display_name() + " has nothing to say.")

    def chat_open(self, player) -> Dict[str, Any]:
        """Start conversation. Returns opening line + 3 Jean options."""
        try:
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
                    "reputation": getattr(player, "reputation", {}).get(self.name, 0),
                }

            self._ensure_personality(player)
            system = self._build_system_prompt(player)
            adapter = self._get_adapter()
            llm_available = adapter is not None and adapter.enabled

            # Generate the NPC opening (and, on a combined adapter, Jean's options
            # in the same call). Opening lines never drain loquacity.
            turn = self._run_npc_turn(
                adapter, system, llm_available, is_opening=True, jean_text=None
            )
            if turn is not None:
                npc_opening = turn["npc_text"]
            else:
                npc_opening = self._get_fallback_npc_line(is_opening=True, player=player)
                llm_available = False

            jean_options = self._resolve_jean_options(turn, adapter, npc_opening, 0)

            game_tick = getattr(getattr(player, "universe", None), "game_tick", 0) or 0
            chapter = self._get_chapter(player)
            self._save_exchange_to_persistence(
                player, npc_opening, "", game_tick, chapter
            )

            return {
                "success": True,
                "npc_key": npc_key,
                "npc_name": self._display_name(),
                "npc_opening": npc_opening,
                "npc_flavor": turn.get("npc_flavor", "") if turn else "",
                "jean_options": jean_options,
                "loquacity_current": self.loquacity_current,
                "loquacity_max": self.loquacity_max,
                "turn": 0,
                "llm_available": llm_available,
                "conversation_ended": False,
                "reputation": getattr(player, "reputation", {}).get(self.name, 0),
            }
        except Exception as e:
            logger.error(f"ConversationalNPCMixin.chat_open error: {e}")
            return {"success": False, "error": str(e)}

    def chat_respond(self, player, jean_text: str, jean_tone: str) -> Dict[str, Any]:
        """Process Jean's response. Returns NPC reply + 3 new Jean options."""
        try:
            self._compute_loquacity(player)
            npc_key = self._get_npc_key(player)
            self._load_history_from_persistence(player)

            # Update last history entry with jean_text, or append new
            if self._chat_history and not self._chat_history[-1].get("jean"):
                self._chat_history[-1]["jean"] = jean_text
            else:
                game_tick = (
                    getattr(getattr(player, "universe", None), "game_tick", 0) or 0
                )
                chapter = self._get_chapter(player)
                self._chat_history.append(
                    {
                        "npc": "",
                        "jean": jean_text,
                        "game_tick": game_tick,
                        "chapter": chapter,
                    }
                )

            self._ensure_personality(player)
            system = self._build_system_prompt(player)
            adapter = self._get_adapter()
            llm_available = adapter is not None and adapter.enabled

            # Generate NPC response (combined adapters also return Jean's options)
            turn = self._run_npc_turn(
                adapter, system, llm_available, is_opening=False, jean_text=jean_text
            )
            conversation_quality = "neutral"
            reputation_delta = 0
            loquacity_delta = None
            npc_response = None
            npc_flavor = ""

            if turn is not None:
                npc_response = turn["npc_text"]
                npc_flavor = turn.get("npc_flavor", "") or ""
                conversation_quality = turn["conversation_quality"]
                reputation_delta = turn["reputation_delta"]
                loquacity_delta = turn["loquacity_delta"]

            # Apply loquacity change. The LLM may signal a signed delta (usually a
            # drain, occasionally a GAIN when Jean raises a topic the NPC finds
            # interesting). When no explicit delta is supplied (legacy adapter or
            # deterministic fallback), fall back to the quality-based drain so
            # conversations still wind down.
            if loquacity_delta is None:
                loquacity_delta = -_LOQUACITY_DRAIN.get(conversation_quality, 8)
            loquacity_delta = max(-40, min(15, int(loquacity_delta)))
            self.loquacity_current = max(
                0, min(self.loquacity_max, self.loquacity_current + loquacity_delta)
            )

            # Resolved once here (rather than separately for the fallback-line
            # decision and the later response payload) so the two can never
            # drift out of sync.
            conversation_ended = self.loquacity_current < self.loquacity_threshold

            # Fall back only after loquacity is resolved, so a fallback line can
            # tell whether this exchange is actually ending the conversation
            # (use a "done talking" closing line) or just a mid-conversation LLM
            # hiccup (use in-character filler instead of a false goodbye).
            if npc_response is None:
                npc_response = self._get_fallback_npc_line(
                    is_opening=False, player=player, exhausted=conversation_ended
                )
                llm_available = False

                # Authored fallback pools are small (often 3 lines), so a
                # conversation that leans on fallback for several turns in a
                # row (LLM disabled, or repeatedly failing QC) will otherwise
                # cycle back to a line already said earlier in THIS
                # conversation. Rotation alone can't prevent that once the
                # pool wraps, so once it does, end the conversation gracefully
                # instead of visibly repeating.
                #
                # Every row currently in self._chat_history is a genuinely
                # prior statement at this point — including the last one: the
                # "fill jean into last entry" step above already completed it
                # with Jean's current line before this fallback was generated,
                # and this round's own response hasn't been persisted yet (that
                # happens further down). So the comparison set is the full
                # list, not history[:-1] — slicing off the last entry would
                # blind the check to a duplicate against the single most
                # recent line (visible whenever an authored pool has only one
                # entry, since rotation itself only guarantees no two
                # *consecutive* draws collide for pools of two or more).
                already_said = {
                    entry.get("npc") for entry in self._chat_history if entry.get("npc")
                }
                if not conversation_ended and npc_response in already_said:
                    conversation_ended = True
                    npc_response = self._get_fallback_npc_line(
                        is_opening=False, player=player, exhausted=True
                    )

            # Apply the NPC's in-character reaction to Jean's reputation
            if not hasattr(player, "reputation"):
                player.reputation = {}
            old_reputation = player.reputation.get(self.name, 0)
            new_reputation = max(-100, min(100, old_reputation + reputation_delta))
            player.reputation[self.name] = new_reputation

            # Persist exchange as a new row awaiting Jean's next line, mirroring
            # chat_open's row shape ({npc: <this line>, jean: ""}) so next
            # round's "fill jean into last entry" step (top of this method)
            # updates it in place instead of falling into that step's own
            # append-a-placeholder branch. Passing the real jean_text here
            # (as this used to) made BOTH that fill step AND this persist call
            # append a row every single round — every turn was saved twice,
            # once as a bare {npc: "", jean: ...} placeholder and once
            # complete. jean_text="" avoids that, and also keeps
            # _format_history's per-row "NPC line, then Jean line" print order
            # chronologically correct (Jean's reply prints right after the
            # line it replied to, not attached to the line it *prompted*).
            # conversation_count is bumped separately since it no longer rides
            # on _save_exchange_to_persistence's own jean_text-truthy check.
            game_tick = getattr(getattr(player, "universe", None), "game_tick", 0) or 0
            chapter = self._get_chapter(player)
            self._save_exchange_to_persistence(
                player, npc_response, "", game_tick, chapter
            )
            self._bump_conversation_count(player)

            # Jean's options for the next round. Once loquacity is spent the
            # options are omitted so the NPC's own (lore- and context-aware) reply
            # stands as the graceful closing line, with nothing left to say back.
            jean_options: List[Dict[str, str]] = []
            if not conversation_ended:
                turn_number = len(self._chat_history)
                jean_options = self._resolve_jean_options(
                    turn, adapter, npc_response, turn_number
                )

            return {
                "success": True,
                "npc_key": npc_key,
                "npc_response": npc_response,
                "npc_flavor": npc_flavor,
                "jean_options": jean_options,
                "conversation_quality": conversation_quality,
                "loquacity_current": self.loquacity_current,
                "loquacity_max": self.loquacity_max,
                "turn": len(self._chat_history),
                "llm_available": llm_available,
                "conversation_ended": conversation_ended,
                "reputation": new_reputation,
                "reputation_delta": reputation_delta,
            }
        except Exception as e:
            logger.error(f"ConversationalNPCMixin.chat_respond error: {e}")
            return {"success": False, "error": str(e)}

    def loquacity_tick(self):
        """Recover loquacity each game beat (called outside active conversation)."""
        if self.loquacity_max == 0:
            return  # Not yet initialised; skip until first conversation
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

    def _next_from_pool(self, pool: List[str]) -> Optional[str]:
        """Return the next line from ``pool``, rotating via the NPC-line index.

        Always advances the counter (even for a single-entry pool) so repeated
        fallback calls stay predictable and never silently reset. Uses
        ``getattr``/instance-``setattr`` rather than assuming
        ``_chat_npc_fallback_idx`` was set by ``_init_chat_attrs`` — minimal
        NPC test doubles and any future caller that skips full init still
        rotate correctly instead of raising ``AttributeError``.
        """
        if not pool:
            return None
        idx = getattr(self, "_chat_npc_fallback_idx", 0)
        line = pool[idx % len(pool)]
        self._chat_npc_fallback_idx = idx + 1
        return line

    def _get_fallback_npc_line(
        self, is_opening: bool, player, exhausted: bool = False
    ) -> str:
        """Get fallback NPC line (no LLM).

        Rotates through the NPC's authored line pool instead of always
        returning the first entry — a stalled/unavailable LLM used to make
        every fallback turn (opening AND every mid-conversation reply) return
        the exact same string, which read as the NPC repeating itself.

        ``exhausted`` distinguishes a genuinely ending conversation (loquacity
        below threshold — use the authored "done talking" closing lines) from
        a mid-conversation LLM hiccup (conversation continues — reusing a
        closing line here would falsely tell the player the NPC is done).
        """
        if self._chat_char_config:
            chapter = self._get_chapter(player)
            starters = self._chat_char_config.get(
                "conversation_starters_by_chapter", {}
            ).get(chapter, [])
            closing = self._chat_char_config.get("closing_lines_when_exhausted", [])

            if is_opening:
                line = self._next_from_pool(starters)
                if line:
                    return line
            elif exhausted:
                line = self._next_from_pool(closing) or self._next_from_pool(starters)
                if line:
                    return line
            else:
                # Mid-conversation and not exhausted: chapter-flavor starters
                # read as plausible filler without implying the NPC is done.
                line = self._next_from_pool(starters) or self._next_from_pool(closing)
                if line:
                    return line
        else:
            # Generic nomad: rotate through a small pool derived from the
            # generated personality so the same speech sample doesn't repeat
            # verbatim on every fallback turn.
            pers = self._chat_personality or {}
            speech = pers.get("speech_sample")
            knowledge = pers.get("knowledge") or []
            given_name = pers.get("given_name", "They")
            pool = [
                text
                for text in (
                    speech,
                    f"{given_name} falls quiet a moment, considering." if speech else None,
                    f"Ask again about {knowledge[0]}, maybe." if knowledge else None,
                )
                if text
            ]
            line = self._next_from_pool(pool)
            if line:
                return line

        return "Nothing to say right now."

    def _get_fallback_jean_options(self) -> List[Dict[str, str]]:
        """Return fallback Jean options, cycling through pool."""
        pool = _JEAN_FALLBACK_POOL[self._chat_fallback_idx % len(_JEAN_FALLBACK_POOL)]
        self._chat_fallback_idx += 1
        return pool
