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
    self.keywords            list[str] (must already include "talk")

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
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import _chat_guard
from ._llm import _load_llm_client_module
from src.narration import narrate

logger = logging.getLogger(__name__)

_AI_DIR = Path(__file__).resolve().parent.parent.parent / "ai"
_HUMAN_NPC_DIR = _AI_DIR / "npc" / "human"
_WORLD_FACTS_PATH = _HUMAN_NPC_DIR / "world_facts.json"

# Modern slang / anachronism blocklist (regex pattern). Note: "you know?" ends
# in a non-word char, so it must sit OUTSIDE the trailing \b group — inside it,
# \b after "?" only matches when a word character follows, which made that
# alternative dead at end-of-sentence (its only realistic position).
_SLANG_PATTERN = re.compile(
    r"\b(?:okay|hey there|yeah|yep|nope|awesome|literally|basically|"
    r"gonna|wanna|gotta|no worries|guns?|bombs?|bullets?|internet)\b"
    r"|\byou know\?"
    # "cool" is period-correct as a temperature/temperament word ("the cool
    # water", "a cool head"); only the bare interjection — sentence-final or
    # followed by a comma — is slang.
    r"|\bcool(?=\s*(?:[,.!?]|$))",
    re.IGNORECASE,
)

# Jean-dialogue guard: reject if NPC text writes Jean's dialogue or narrates
# Jean speaking (past OR present tense — models narrate in both).
_JEAN_DIALOG_PATTERN = re.compile(
    r"\bjean\s+(said|says|replied|replies|asked|asks|answered|answers|"
    r"told|tells)\b|jean:\s*",
    re.IGNORECASE,
)

# Roleplay action asides: models frequently put stage directions inside the
# spoken line as *asterisk actions* ("*nods slowly* Fine.") even though
# npc_flavor is the designated home for physical beats. These are extracted
# and relocated, never shown verbatim.
_BOLD_MD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
_ACTION_ASIDE_PATTERN = re.compile(r"\*([^*\n]{2,160})\*")

# Sentence splitter — shared with _chat_guard, which owns the definition and
# the terminator-preserving rationale comment. Aliased under this module's
# existing name so its one call site (in _qc_npc_text_ex) stays untouched.
_SENTENCE_PATTERN = _chat_guard._SENTENCE_PATTERN

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


# QC pipeline size/count/similarity thresholds, named so the numbers used in
# _qc_npc_text_ex / _qc_flavor_text / _qc_jean_options / _top_up_jean_options
# read as policy rather than unexplained literals scattered through the file.
_MAX_NPC_TEXT_CHARS = 300  # NPC line truncation cap (_qc_npc_text_ex step 2)
_MAX_OPTION_CHARS = 160  # Jean dialogue option length cap
_MAX_FLAVOR_CHARS = 200  # npc_flavor truncation cap
_JEAN_OPTION_COUNT = 3  # Jean is always offered exactly three options
_OPTION_SIMILARITY_MAX = 0.6  # Jaccard ceiling before two options count as duplicates
_NPC_REPEAT_SIMILARITY = 0.7  # Jaccard floor before an NPC line counts as a repeat

# Meta-speech markers ("[Option 2]", "As Jean, I...") that mean the model
# broke character while generating one of Jean's dialogue options. Hoisted to
# module level (compiled once) rather than re-built on every option checked
# in _qc_jean_options.
_OPTION_META_PATTERN = re.compile(
    r"\[Option|\bAs Jean\b|I don.t know what to say", re.IGNORECASE
)

# Fallback drain amounts keyed by conversation_quality — used only when the LLM
# does not supply an explicit signed loquacity_delta (legacy adapter / fallback).
_LOQUACITY_DRAIN = {"positive": 3, "neutral": 8, "negative": 15, "offensive": 30}

# Craft vocabulary a progressing ally is licensed to teach about. The system
# prompt's COMBAT SELF-KNOWLEDGE block exists precisely so an ally can discuss
# its own growth, so these keep the state guard from rewriting intended content.
# They only ever excuse a teaching/growth flag — never a handover or a promise.
_ALLY_CRAFT_TOPICS = frozenset(
    {
        "technique",
        "techniques",
        "guard",
        "grip",
        "stance",
        "footwork",
        "swordwork",
        "craft",
        "training",
        "practice",
        "fight",
        "fighting",
    }
)

# Words that carry no subject matter, dropped when knowledge_scope entries are
# reduced to guard topics. A topic only ever excuses a teaching/growth flag, but
# it excuses it for the whole sentence, so a generic word slipping through
# switches that half of the guard off for the character entirely: the authored
# scopes yield "will" (Liss), "like"/"wait" (Devet) and "work"/"knows"
# (Vespera), each of which would excuse almost any teaching offer they make.
_TOPIC_STOPWORDS = frozenset(
    {
        # structural
        "that",
        "this",
        "with",
        "from",
        "their",
        "them",
        "they",
        "when",
        "what",
        "which",
        "about",
        "into",
        "over",
        "have",
        "been",
        "some",
        "than",
        "then",
        "there",
        "where",
        "while",
        "would",
        "could",
        "should",
        "because",
        "other",
        "your",
        "yours",
        # generic verbs / adjectives / adverbs with no subject matter
        "anyone",
        "better",
        "everyone",
        "know",
        "knows",
        "like",
        "look",
        "many",
        "more",
        "most",
        "much",
        "need",
        "noticed",
        "people",
        "rather",
        "really",
        "take",
        "tell",
        "things",
        "think",
        "very",
        "wait",
        "want",
        "will",
        "work",
        # Jean is the listener, never a subject the guard should excuse
        "jean",
    }
)

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

# Generic nomad fallbacks (selected via a stable crc32 digest, not the
# built-in hash(), so the pick is deterministic across process restarts)
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

        # "talk" is already present on every host class's base keywords
        # (Friend, Merchant); it alone opens the LLM chat panel client-side,
        # so we deliberately do not also add "chat" as a second, redundant
        # button (see chat()/InteractPanel.jsx — both keywords routed to the
        # same panel, which meant NPCs showed two buttons for one action).
        if not hasattr(self, "keywords"):
            self.keywords = []

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

        # Store personality for generics
        if self._chat_personality:
            entry["personality"] = self._chat_personality

    def _bump_conversation_count(self, player) -> None:
        """Increment conversation_count for a completed respond round.

        Both call sites of _save_exchange_to_persistence pass jean_text="" —
        chat_open always has (there is no Jean line at the opening) and
        chat_respond persists its new row with jean_text="" (see its call
        site) so the row shape matches chat_open's and next round's history
        fill-in works correctly. A jean_text-truthy increment inside
        _save_exchange_to_persistence itself would therefore never fire for
        either caller, so this method is the single, explicit owner of the
        counter, called right after a call that is guaranteed to have already
        created the persisted entry.
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
            # Prevention half of the state guard: nothing said in a chat reaches
            # the engine, so an offer or an appointment is a promise the game
            # cannot keep. Cheaper to not generate one than to catch and revise
            # it (see src/npc/_chat_guard.py). Terse by design — this block is
            # static and re-sent every round.
            "Talk changes nothing here: never give, lend, sell, mend, or hand "
            "anything over; never travel with Jean or promise to meet him later; "
            "never describe his belongings, wounds, or coin — you cannot see "
            "them. Speak of such things in the past or in general instead.\n"
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

        # Fallback if LLM unavailable. crc32 (not the built-in hash()) because
        # hash() is salted per process — the "deterministic" pick would
        # otherwise change every restart.
        if not self._chat_personality:
            key = self._chat_npc_key or self.name
            idx = zlib.crc32(key.encode("utf-8")) % len(_GENERIC_FALLBACKS)
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

    # ------------------------------------------------------------------
    # NPC-text QC pipeline
    # ------------------------------------------------------------------

    @staticmethod
    def _cleanup_removed_spans(text: str) -> str:
        """Repair the holes left by removing a span from a sentence.

        Collapses whitespace, closes gaps before punctuation, deduplicates
        commas, and strips orphan leading/trailing punctuation — so removing
        "cool" from "that's cool, okay" yields "that's" rather than
        "that's  , ".
        """
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\s+([,.!?;:])", r"\1", text)
        text = re.sub(r"([,;:])(?:\s*\1)+", r"\1", text)
        # A removed sentence-final span leaves its comma glued to the
        # terminator ("It's fine, cool." -> "It's fine,."): drop it.
        text = re.sub(r"[,;:]+(?=[.!?])", "", text)
        # Strip leading separators — but a leading ellipsis is intentional
        # hesitation ("...fine."), not an orphan, so keep it.
        text = re.sub(r"^[\s,;:]+", "", text)
        if not text.startswith("..."):
            text = re.sub(r"^[.!?]+[\s,;:]*", "", text)
        text = re.sub(r"[\s,;:]+$", "", text)
        return text.strip()

    @staticmethod
    def _capitalize_sentence_starts(text: str) -> str:
        """Upper-case the first letter at text start or after `.`/`!`/`?`.

        The lookbehind keeps an ellipsis from counting as a sentence end, so
        "Well... maybe." is not rewritten to "Well... Maybe.".
        """
        return re.sub(
            r"(^|(?<!\.\.)[.!?]\s+)([a-z])",
            lambda m: m.group(1) + m.group(2).upper(),
            text,
        )

    def _extract_action_asides(self, text: str) -> tuple:
        """Pull *asterisk action* stage directions out of spoken text.

        Returns (text_without_asides, aside_text). Markdown bold markers are
        unwrapped (the words stay), single-asterisk spans at a sentence
        boundary (start of text, after terminal punctuation, or end of text)
        are stage directions and are extracted for relocation into npc_flavor,
        single-asterisk spans embedded mid-sentence are markdown emphasis and
        are unwrapped in place ("I would *never* sell" keeps "never"), and
        stray markers are dropped.
        """
        if "*" not in text:
            return text, ""
        text = _BOLD_MD_PATTERN.sub(r"\1", text)
        asides: List[str] = []

        def _classify(match: "re.Match") -> str:
            before = text[: match.start()].rstrip()
            after = text[match.end():].lstrip()
            # "*" counts as a boundary so consecutive asides ("*nods*
            # *smiles* Fine.") are both extracted — the second one sees the
            # first's not-yet-substituted "*" as its left neighbour.
            at_boundary = (
                not before or before[-1] in ".!?\"'*" or not after
            )
            if at_boundary:
                inner = match.group(1).strip()
                if inner:
                    asides.append(inner)
                return " "
            return match.group(1)

        text = _ACTION_ASIDE_PATTERN.sub(_classify, text)
        text = text.replace("*", " ")
        return self._cleanup_removed_spans(text), " ".join(asides)

    def _allowed_noun_tokens(self) -> set:
        """Lowercased single-word tokens the proper-noun scan must not touch.

        Multi-word allowlist entries ("Echoing Caves", "Pillar Readers") are
        split into their component tokens — the scan matches token-by-token, so
        checking tokens against the full-string allowlist rejected every word
        of a legitimate multi-word name ("the Echoing Caves" used to come out
        as "the they they"). Also includes this NPC's own name and, for
        generics, the generated given_name — an NPC must be able to say its
        own name.
        """
        tokens: set = set()
        sources: List[str] = list(
            (getattr(self, "_chat_world_facts", None) or {}).get(
                "allowed_proper_nouns", []
            )
        )
        sources.extend(["Jean", "Gorran", str(getattr(self, "name", "") or "")])
        personality = getattr(self, "_chat_personality", None) or {}
        given = personality.get("given_name")
        if given:
            sources.append(str(given))
        for noun in sources:
            for part in str(noun).replace("-", " ").split():
                tokens.add(part.lower())
        return tokens

    @staticmethod
    def _is_allowed_noun(low: str, allowed: set) -> bool:
        """Token-level allowlist check with light inflection tolerance.

        Accepts exact matches, singular/plural variants (Golemite/Golemites),
        and adjectival extensions of an allowed stem of 5+ chars
        (Grondia -> Grondian).
        """
        if low in allowed:
            return True
        if low.endswith("s") and low[:-1] in allowed:
            return True
        if low + "s" in allowed:
            return True
        return any(len(a) >= 5 and low.startswith(a) for a in allowed)

    def _find_invented_nouns(self, text: str) -> Dict[str, str]:
        """Map each invented proper noun in ``text`` to its safe replacement.

        Skips allowed nouns, common English capitalized words, and tokens that
        merely begin a sentence. Replacements are grammatical in both subject
        and object position: "someone" for people/groups, "that place" for
        place-shaped endings ("he met they" was the old failure mode).
        """
        allowed = self._allowed_noun_tokens()

        def _is_sentence_initial(match_start: int) -> bool:
            j = match_start - 1
            while j >= 0 and text[j].isspace():
                j -= 1
            return j < 0 or text[j] in ".!?\"'"

        def _is_known(low: str) -> bool:
            return low in _COMMON_CAP_WORDS or self._is_allowed_noun(low, allowed)

        replacements: Dict[str, str] = {}
        for match in _CAP_TOKEN_PATTERN.finditer(text):
            token = match.group(1)
            if token in replacements:
                continue
            # Hyphenated tokens: a descriptive compound ("East-bank") has a
            # known first part and a lowercase remainder; an invented compound
            # ("Kel-Thar") capitalizes its parts. Plain tokens just need to
            # be known.
            raw_parts = [p for p in token.split("-") if p]
            if len(raw_parts) > 1:
                if _is_known(raw_parts[0].lower()) and all(
                    p == p.lower() for p in raw_parts[1:]
                ):
                    continue
            if all(_is_known(p.lower()) for p in raw_parts):
                continue
            if _is_sentence_initial(match.start()):
                continue
            replacements[token] = (
                "that place" if token.endswith(("ia", "on", "or")) else "someone"
            )
        return replacements

    def _qc_npc_text(
        self, text: str, history: List[Dict[str, Any]], allow_rewrite: bool = True
    ) -> Optional[str]:
        """Apply QC pipeline. Return cleaned text or None.

        Compatibility wrapper over ``_qc_npc_text_ex`` (which also reports the
        rejection reason and any extracted action aside).
        """
        cleaned, _reason, _aside = self._qc_npc_text_ex(
            text, history, allow_rewrite=allow_rewrite
        )
        return cleaned

    def _qc_npc_text_ex(
        self, text: str, history: List[Dict[str, Any]], allow_rewrite: bool = True
    ) -> tuple:
        """QC pipeline core. Returns (cleaned_text_or_None, reason, action_aside).

        Policy (per design decision): content violations — invented proper
        nouns, modern slang, prohibited phrases — REJECT the line when
        ``allow_rewrite`` is False so the caller can retry with guidance, and
        are repaired in place on the final attempt so a good line is never
        discarded over one word. Structural problems (Jean-dialogue, repetition,
        empty text) always reject; mechanical normalization (length caps,
        punctuation) always applies.
        """
        original = text
        # Step 1: extract roleplay *action* asides, then strip / garbage check
        text, aside = self._extract_action_asides(text.strip())
        text = text.strip()
        if not _has_real_npc_text(text):
            logger.debug("_qc_npc_text rejected: no real text after strip. original=%r", original)
            return None, "the reply had no spoken text", aside
        if aside and text[0].islower():
            # The spoken line started after a leading aside ("*shrugs* fine.")
            text = text[0].upper() + text[1:]

        # Step 2: Truncate at sentence boundary if too long
        if len(text) > _MAX_NPC_TEXT_CHARS:
            boundary_pos = -1
            for i in range(_MAX_NPC_TEXT_CHARS - 1, -1, -1):
                if text[i] in ".!?":
                    boundary_pos = i + 1
                    break
            text = (
                text[:boundary_pos].strip()
                if boundary_pos > 0
                else text[:_MAX_NPC_TEXT_CHARS].strip()
            )

        # Step 3: Reject if Jean-dialogue pattern found (always a rejection —
        # the NPC must never speak for Jean, and there is no safe rewrite)
        if _JEAN_DIALOG_PATTERN.search(text):
            logger.debug("_qc_npc_text rejected: Jean-dialogue pattern. text=%r", text)
            return None, "it wrote Jean's dialogue or narrated Jean speaking", aside

        # Step 4: Invented proper noun scan
        replacements = self._find_invented_nouns(text)
        rewrote = False
        if replacements:
            if not allow_rewrite:
                logger.debug("_qc_npc_text rejected: invented nouns %s. text=%r", sorted(replacements), text)
                return (
                    None,
                    "it used names not in the allowed list: "
                    + ", ".join(sorted(replacements)),
                    aside,
                )
            for token, repl in replacements.items():
                text = re.sub(r"\b" + re.escape(token) + r"\b", repl, text)
            rewrote = True

        # Step 5: Slang filter
        if _SLANG_PATTERN.search(text):
            if not allow_rewrite:
                logger.debug("_qc_npc_text rejected: slang. text=%r", text)
                return None, "it used modern slang or anachronistic wording", aside
            text = self._cleanup_removed_spans(_SLANG_PATTERN.sub(" ", text))
            rewrote = True
            if not _has_real_npc_text(text):
                logger.debug("_qc_npc_text rejected: no real text after slang filter. text=%r", text)
                return None, "nothing remained after removing slang", aside

        # Step 6: Prohibited phrases (story chars only, patterns pre-compiled
        # in _init_chat_attrs). Removed cleanly — the old "[...]" placeholder
        # was a visible artifact in player-facing dialogue.
        for pattern in self._prohibited_patterns:
            if pattern.search(text):
                if not allow_rewrite:
                    logger.debug("_qc_npc_text rejected: prohibited phrase. text=%r", text)
                    return None, "it used a phrase this character must never say", aside
                text = self._cleanup_removed_spans(pattern.sub(" ", text))
                rewrote = True
        if not _has_real_npc_text(text):
            logger.debug("_qc_npc_text rejected: no real text after prohibited filter. text=%r", text)
            return None, "nothing remained after removing prohibited phrasing", aside

        # Step 7: Repetition guard — caller's retry loop handles the second attempt
        for prior in history[-8:]:
            prior_npc = prior.get("npc", "")
            if prior_npc and self._jaccard(text, prior_npc) > _NPC_REPEAT_SIMILARITY:
                logger.debug("_qc_npc_text rejected: repetition guard. jaccard=%.2f text=%r prior=%r", self._jaccard(text, prior_npc), text, prior_npc)
                return None, "it repeated a line already said earlier in this conversation", aside

        # Step 8: Sentence cap (keep first 3 sentences, preserving each
        # sentence's own terminator) + terminal punctuation. A fragment with
        # no alphanumeric content (a closing quote split off by the sentence
        # regex) belongs to the previous sentence, not the cap count —
        # otherwise 'He called it "the long road."' gains a stray period.
        sentences: List[str] = []
        for raw_sentence in _SENTENCE_PATTERN.findall(text):
            piece = raw_sentence.strip()
            if not piece:
                continue
            if sentences and not any(ch.isalnum() for ch in piece):
                sentences[-1] += piece
                continue
            sentences.append(piece)
        # The sentence regex can't capture a leading ellipsis (it requires a
        # non-terminator first), so re-attach intentional hesitation.
        if sentences and text.lstrip().startswith("..."):
            sentences[0] = "..." + sentences[0]
        text = " ".join(sentences[:3])
        # Terminal punctuation — looking through a closing quote so
        # '... road."' does not gain a stray period after the quote.
        if text and text.rstrip("\"'”’")[-1:] not in (".", "!", "?", ""):
            text += "."

        # Step 9: If substitutions ran, repair capitalization at sentence starts
        if rewrote:
            text = self._capitalize_sentence_starts(text)

        logger.debug("_qc_npc_text passed. cleaned_chars=%s original_chars=%s", len(text), len(original))
        return text, None, aside

    def _qc_flavor_text(self, flavor: str) -> str:
        """Rewrite-only QC for npc_flavor. Returns cleaned flavor or "".

        Flavor is decorative — it is never worth failing a whole turn over, so
        this never rejects: invented nouns are substituted, slang removed,
        markers stripped, and anything left unusable simply drops the flavor.
        """
        if not flavor:
            return ""
        flavor = _BOLD_MD_PATTERN.sub(r"\1", str(flavor)).replace("*", " ").strip()
        for token, repl in self._find_invented_nouns(flavor).items():
            flavor = re.sub(r"\b" + re.escape(token) + r"\b", repl, flavor)
        flavor = self._cleanup_removed_spans(_SLANG_PATTERN.sub(" ", flavor))
        if not _has_real_npc_text(flavor):
            return ""
        flavor = flavor[:_MAX_FLAVOR_CHARS].strip()
        if flavor[-1] not in ".!?":
            flavor += "."
        if flavor[0].islower():
            flavor = flavor[0].upper() + flavor[1:]
        return flavor

    def _qc_jean_options(self, options: Any) -> Optional[List[Dict[str, str]]]:
        """QC Jean dialogue options. Return the salvageable subset, or None.

        Per design decision this salvages rather than rejecting wholesale: each
        option is validated independently, near-duplicates drop only the later
        member of the pair, and the caller tops the set back up to three from
        the fallback pool. One malformed option no longer throws away two good,
        context-aware ones.
        """
        if not isinstance(options, list) or not options:
            return None

        expected_tones = ["direct", "guarded", "open"]
        validated = []
        for i, opt in enumerate(options[:_JEAN_OPTION_COUNT]):
            if not isinstance(opt, dict) or "text" not in opt:
                continue

            text = str(opt.get("text", "")).strip()
            if not (5 <= len(text) <= _MAX_OPTION_CHARS):
                continue

            # No meta-speech
            if _OPTION_META_PATTERN.search(text):
                continue

            tone = str(opt.get("tone", expected_tones[i % _JEAN_OPTION_COUNT])).lower()
            if tone not in ("direct", "guarded", "open"):
                tone = expected_tones[i % _JEAN_OPTION_COUNT]

            validated.append({"tone": tone, "text": text})

        # Dedup: keep the earlier of any too-similar pair
        deduped: List[Dict[str, str]] = []
        for opt in validated:
            if all(
                self._jaccard(opt["text"], kept["text"]) <= _OPTION_SIMILARITY_MAX
                for kept in deduped
            ):
                deduped.append(opt)

        return deduped or None

    def _top_up_jean_options(
        self, options: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Fill a partial option set up to three from the fallback pool.

        Prefers pool entries whose tone is not already covered, skips any that
        read too close to a kept option, and pads unconditionally as a last
        resort so the player always sees three choices.
        """
        options = [dict(o) for o in options[:_JEAN_OPTION_COUNT]]
        if len(options) >= _JEAN_OPTION_COUNT:
            return options
        pool = self._get_fallback_jean_options()
        used_tones = {o["tone"] for o in options}
        for fb in pool:
            if len(options) >= _JEAN_OPTION_COUNT:
                break
            if fb["tone"] in used_tones:
                continue
            if any(
                self._jaccard(fb["text"], o["text"]) > _OPTION_SIMILARITY_MAX
                for o in options
            ):
                continue
            options.append(dict(fb))
            used_tones.add(fb["tone"])
        for fb in pool:
            if len(options) >= _JEAN_OPTION_COUNT:
                break
            if any(fb["text"] == o["text"] for o in options):
                continue
            options.append(dict(fb))
        return options

    # ------------------------------------------------------------------
    # Adversarial state-implication guard
    # ------------------------------------------------------------------

    def _guard_allowed_topics(self) -> set:
        """Subject matter this NPC is deliberately licensed to speak about.

        Some real game state is fed into the system prompt on purpose: a
        progressing ally's own techniques and growth (COMBAT SELF-KNOWLEDGE),
        Gorran's speech stage (JEAN'S KNOWN CONTEXT), and a story character's
        authored ``knowledge_scope``. Naming those here keeps intended content
        out of the reviser's way. The licence is narrow by construction — a
        topic can only excuse a teaching/growth flag, never a handover or an
        appointment (see ``_chat_guard._EXCUSABLE_SUBCATEGORIES``), so a
        knowledge_scope entry like "the ferry crossing" can never license
        "I'll give you a knife for the crossing".
        """
        topics = {"gorran"}
        if getattr(self, "growth_profile", None):
            topics |= set(_ALLY_CRAFT_TOPICS)
            for move in getattr(self, "known_moves", None) or []:
                name = getattr(move, "name", "")
                if name:
                    topics.add(str(name).lower())
        config = getattr(self, "_chat_char_config", None) or {}
        for entry in config.get("knowledge_scope") or []:
            for word in re.findall(r"[a-z]{4,}", str(entry).lower()):
                if word not in _TOPIC_STOPWORDS:
                    topics.add(word)
        return topics

    def _request_guard_revision(
        self, adapter, system: str, npc_text: str, options: List[Dict[str, str]], flags
    ) -> Optional[Dict[str, Any]]:
        """Ask the model to steer a flagged turn away from what tripped the guard.

        The only place the guard spends an LLM call, and only on a tripped turn.
        Returns None when there is no reviser or the call fails, which drops the
        caller onto the deterministic hedge.
        """
        if adapter is None or not hasattr(adapter, "revise_turn"):
            logger.info(
                "_guard_turn no reviser available (adapter=%s); using deterministic hedge.",
                type(adapter).__name__ if adapter is not None else None,
            )
            return None
        try:
            revision = adapter.revise_turn(
                system, npc_text, options, _chat_guard.guidance_for(flags)
            )
            # A nonconforming adapter returning a truthy non-dict would crash
            # the caller's .get() outside any guard — treat it as no revision.
            return revision if isinstance(revision, dict) else None
        except Exception as e:  # provider errors must never cost the player a turn
            logger.warning("_request_guard_revision revise_turn failed: %s", e)
            return None

    def _guard_turn(
        self,
        adapter,
        system: str,
        npc_text: str,
        npc_flavor: str,
        jean_options: List[Dict[str, str]],
    ) -> tuple:
        """Strip implied game-state changes from a turn before the player sees it.

        Conversations are lore only — nothing said in one is wired to the engine
        — so an offered blade, an offered escort, a claim about Jean's pack, or a
        meeting arranged for dawn is a promise the game cannot keep. Returns
        ``(npc_text, npc_flavor, jean_options)``.

        Costs nothing when the tripwire stays quiet, which is the common case. A
        tripped turn spends at most one extra call; if that call is unavailable
        or comes back still dirty, the deterministic hedge ships instead, so the
        player always gets a turn.
        """
        options = [dict(o) for o in (jean_options or [])]
        topics = self._guard_allowed_topics()
        text_flags = _chat_guard.scan_npc_text(npc_text or "", topics)
        flavor_flags = _chat_guard.scan_npc_text(npc_flavor or "", topics)
        option_flags = [
            _chat_guard.scan_option_text(o.get("text", ""), topics) for o in options
        ]
        all_flags = list(text_flags) + list(flavor_flags)
        for flags in option_flags:
            all_flags.extend(flags)
        if not all_flags:
            return npc_text, npc_flavor, options

        logger.info(
            "_guard_turn tripwire hit npc=%s categories=%s line_flags=%s flavor_flags=%s option_flags=%s",
            getattr(self, "name", "?"),
            sorted({f.category for f in all_flags}),
            len(text_flags),
            len(flavor_flags),
            sum(len(f) for f in option_flags),
        )

        # Only the line and the options can be *repaired*; flagged flavor is
        # dropped outright below. Escalating on flavor alone would spend a real
        # round trip whose answer is then thrown away, so the guidance — and the
        # decision to call at all — is built from the repairable flags only.
        escalation_flags = list(text_flags)
        for flags in option_flags:
            escalation_flags.extend(flags)
        revision = None
        if escalation_flags:
            revision = self._request_guard_revision(
                adapter, system, npc_text, options, escalation_flags
            )

        # NPC line: accept the revision only if it comes back clean; otherwise
        # hedge the original, which is at least a known quantity.
        final_text = npc_text
        if text_flags:
            # The revision comes straight off the provider and has never been
            # through the normal QC pipeline, so it can carry invented proper
            # nouns, slang, or a prohibited phrase that _run_npc_turn would have
            # caught. Clean it the same way before re-scanning it.
            candidate = (revision or {}).get("npc_text")
            if isinstance(candidate, str) and candidate.strip():
                candidate, _reason, _aside = self._qc_npc_text_ex(
                    candidate, self._chat_history, allow_rewrite=True
                )
            else:
                candidate = None
            if candidate and not _chat_guard.scan_npc_text(candidate, topics):
                final_text = candidate
                logger.info("_guard_turn accepted revised npc_text.")
            else:
                final_text = _chat_guard.hedge_npc_text(npc_text, text_flags)
                logger.info("_guard_turn hedged npc_text deterministically.")

        # Flavor is decorative (same policy as _qc_flavor_text) — a flagged beat
        # is dropped rather than rewritten. It is never worth a turn.
        final_flavor = "" if flavor_flags else npc_flavor

        # Options: prefer clean revised options; otherwise drop the soliciting
        # ones and top the set back up from the deterministic pool.
        final_options = options
        if any(option_flags):
            final_options = self._rebuild_guarded_options(
                options, option_flags, revision, topics
            )

        return final_text, final_flavor, final_options

    def _rebuild_guarded_options(
        self,
        options: List[Dict[str, str]],
        option_flags: List[List[Any]],
        revision: Optional[Dict[str, Any]],
        topics: set,
    ) -> List[Dict[str, str]]:
        """Return three clean Jean options after at least one was flagged."""
        rebuilt: List[Dict[str, str]] = []
        revised = (revision or {}).get("jean_options")
        if isinstance(revised, list):
            # Same QC the generated options get (length caps, meta-speech
            # filter, tone defaulting, near-duplicate dedup) — the reviser's
            # output has never seen it, and its own cap is _MAX_FLAVOR_CHARS
            # (200) against _qc_jean_options' _MAX_OPTION_CHARS (160).
            for opt in self._qc_jean_options(revised) or []:
                if _chat_guard.scan_option_text(opt["text"], topics):
                    continue
                rebuilt.append(dict(opt))
        # Salvage policy: clean ORIGINAL options are context-aware and beat
        # generic pool fillers — keep them alongside any clean revised ones
        # (skipping near-duplicates) rather than all-or-nothing replacement.
        for opt, flags in zip(options, option_flags):
            if flags:
                continue
            if any(
                self._jaccard(opt["text"], kept["text"]) > _OPTION_SIMILARITY_MAX
                for kept in rebuilt
            ):
                continue
            rebuilt.append(dict(opt))
        return self._top_up_jean_options(rebuilt)

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
        combined = hasattr(adapter, "generate_turn")
        if combined:
            method, label = adapter.generate_turn, "combined"
        else:
            # Legacy two-call adapter (kept for compatibility with older adapters).
            method, label = adapter.generate_npc_turn, "legacy"
            logger.info(
                "_generate_turn using legacy two-call adapter. is_opening=%s",
                is_opening,
            )
        if is_opening:
            res = method(system, self._chat_history, is_opening=True)
        else:
            res = method(system, self._chat_history, is_opening=False, jean_text=jean_text)
        if not res or not res.get("npc_text"):
            logger.warning(
                "_generate_turn %s adapter returned no npc_text. is_opening=%s keys=%s",
                label,
                is_opening,
                sorted((res or {}).keys()),
            )
            return None
        logger.info(
            "_generate_turn %s adapter succeeded. is_opening=%s npc_text_chars=%s",
            label,
            is_opening,
            len(res.get("npc_text") or ""),
        )
        # Defence in depth: production adapters already coerce and clamp the
        # delta, but a nonconforming value must not raise one frame later in
        # chat_respond's arithmetic.
        try:
            reputation_delta = int(res.get("reputation_delta", 0))
        except (TypeError, ValueError):
            reputation_delta = 0
        return {
            "npc_text": res.get("npc_text"),
            "npc_flavor": res.get("npc_flavor", "") or "",
            "conversation_quality": res.get("conversation_quality", "neutral"),
            "reputation_delta": max(-5, min(5, reputation_delta)),
            "loquacity_delta": res.get("loquacity_delta"),
            "raw_options": res.get("jean_options") if combined else None,
        }

    def _run_npc_turn(
        self, adapter, system: str, llm_available: bool, is_opening: bool, jean_text
    ) -> Optional[Dict[str, Any]]:
        """Produce a QC'd NPC turn, or None if the caller should fall back.

        Attempt 1 runs QC in strict mode: content violations (invented nouns,
        slang, prohibited phrases) reject the line, and the retry carries the
        rejection reason back to the model as corrective guidance — resending
        the identical prompt at the same temperature mostly reproduced the same
        violation. The final attempt runs QC in rewrite mode so a usable line
        is salvaged in place rather than dropping to the deterministic
        fallback. Successful calls are still a single round trip.

        Roleplay *action asides* extracted from the spoken text are relocated
        into npc_flavor (the designated home for physical beats) when the model
        did not supply flavor of its own; flavor then gets its own rewrite-only
        QC pass.
        """
        if not llm_available or adapter is None:
            logger.debug("_run_npc_turn skipped: llm_available=%s has_adapter=%s", llm_available, adapter is not None)
            return None
        max_attempts = 2
        reject_reason: Optional[str] = None
        for attempt in range(1, max_attempts + 1):
            logger.info("_run_npc_turn attempt=%s/%s is_opening=%s", attempt, max_attempts, is_opening)
            sys_prompt = system
            if reject_reason:
                sys_prompt = (
                    system
                    + "\n\n[RETRY GUIDANCE] Your previous reply was rejected by "
                    "quality control because " + reject_reason + ". Write a "
                    "fresh reply that avoids this problem."
                )
            turn = self._generate_turn(adapter, sys_prompt, is_opening, jean_text)
            if turn and turn.get("npc_text"):
                cleaned, reason, aside = self._qc_npc_text_ex(
                    turn["npc_text"],
                    self._chat_history,
                    allow_rewrite=(attempt == max_attempts),
                )
                if cleaned:
                    logger.info("_run_npc_turn QC passed on attempt=%s/%s", attempt, max_attempts)
                    turn["npc_text"] = cleaned
                    flavor = turn.get("npc_flavor") or ""
                    if not flavor and aside:
                        flavor = aside
                    turn["npc_flavor"] = self._qc_flavor_text(flavor)
                    return turn
                reject_reason = reason or "it was unusable"
                logger.warning(
                    "_run_npc_turn QC rejected npc_text on attempt=%s/%s reason=%s text=%r",
                    attempt,
                    max_attempts,
                    reject_reason,
                    # WARNING is default-visible and LOG_FILE-persisted; the
                    # full raw line (which can echo player text) stays on the
                    # DEBUG records inside _qc_npc_text_ex.
                    (turn.get("npc_text") or "")[:80],
                )
            else:
                logger.warning("_run_npc_turn generate_turn returned no npc_text on attempt=%s/%s", attempt, max_attempts)
        logger.error("_run_npc_turn exhausted attempts=%s; caller should use deterministic fallback.", max_attempts)
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
            return self._top_up_jean_options(options or [])
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
                    return self._top_up_jean_options(options)
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
                logger.info("chat_open loquacity cutoff. npc=%s current=%s threshold=%s", self.name, self.loquacity_current, self.loquacity_threshold)
                return {
                    "success": True,
                    "npc_key": npc_key,
                    "npc_name": self._display_name(),
                    "npc_opening": brush_off,
                    "npc_flavor": "",
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
            logger.info("chat_open start npc=%s llm_available=%s has_adapter=%s history_len=%s", self.name, llm_available, adapter is not None, len(self._chat_history))

            # Generate the NPC opening (and, on a combined adapter, Jean's options
            # in the same call). Opening lines never drain loquacity.
            turn = self._run_npc_turn(
                adapter, system, llm_available, is_opening=True, jean_text=None
            )
            if turn is not None:
                npc_opening = turn["npc_text"]
                logger.info("chat_open LLM opening succeeded. npc=%s npc_text_chars=%s", self.name, len(npc_opening))
            else:
                npc_opening = self._get_fallback_npc_line(is_opening=True, player=player)
                llm_available = False
                logger.warning("chat_open using deterministic fallback opening. npc=%s", self.name)

            jean_options = self._resolve_jean_options(turn, adapter, npc_opening, 0)
            logger.info("chat_open resolved jean_options count=%s llm_available=%s", len(jean_options), llm_available)

            # State guard runs on the assembled turn (line + flavor + options)
            # so one escalation call covers all three, and runs BEFORE the
            # persist below: _load_history_from_persistence hands the saved
            # rows straight back to the model next round, so persisting the
            # raw line would feed the implication back in and breed more of
            # them. Only the guarded text is ever written.
            #
            # Only model output is guarded. When turn is None everything here
            # is authored — the fallback opening comes from the character's
            # conversation_starters and the options from _JEAN_FALLBACK_POOL —
            # and the tripwire is not a judge of hand-written lines: Mara's
            # chapter-1 starter says "inventory, not greeting" and Kaelen's
            # closing line says "come back when you need something sharpened",
            # both of which it would replace with a generic hedge (and spend a
            # revision call doing it).
            npc_flavor = turn.get("npc_flavor", "") if turn else ""
            if turn is not None:
                npc_opening, npc_flavor, jean_options = self._guard_turn(
                    adapter, system, npc_opening, npc_flavor, jean_options
                )

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
                "npc_flavor": npc_flavor,
                "jean_options": jean_options,
                "loquacity_current": self.loquacity_current,
                "loquacity_max": self.loquacity_max,
                "turn": 0,
                "llm_available": llm_available,
                "conversation_ended": False,
                "reputation": getattr(player, "reputation", {}).get(self.name, 0),
            }
        except Exception as e:
            # Detail stays server-side (the logger call above); the client
            # never sees raw exception text, which can leak internals.
            logger.error("ConversationalNPCMixin.chat_open error: %s", e, exc_info=True)
            return {"success": False, "error": "Conversation failed — try again."}

    def chat_respond(self, player, jean_text: str, jean_tone: str) -> Dict[str, Any]:
        """Process Jean's response. Returns NPC reply + 3 new Jean options."""
        try:
            # Bound the engine-side copy. The route caps the field at 4000
            # chars, but persisted rows are replayed into every later prompt
            # (last 8 rows), so an over-long line multiplies token spend for
            # the rest of the conversation. 500 chars is generous next to the
            # 300-char NPC lines and 160-char options.
            jean_text = (jean_text or "")[:500]
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
            logger.info("chat_respond start npc=%s llm_available=%s history_len=%s jean_text_chars=%s", self.name, llm_available, len(self._chat_history), len(jean_text or ""))

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
                logger.info("chat_respond LLM turn succeeded. npc=%s npc_text_chars=%s quality=%s", self.name, len(npc_response or ""), conversation_quality)
            else:
                logger.warning("chat_respond LLM turn failed; will use deterministic fallback. npc=%s", self.name)

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
            logger.info("chat_respond loquacity resolved. npc=%s delta=%s current=%s threshold=%s ended=%s", self.name, loquacity_delta, self.loquacity_current, self.loquacity_threshold, conversation_ended)

            # Fall back only after loquacity is resolved, so a fallback line can
            # tell whether this exchange is actually ending the conversation
            # (use a "done talking" closing line) or just a mid-conversation LLM
            # hiccup (use in-character filler instead of a false goodbye).
            if npc_response is None:
                npc_response = self._get_fallback_npc_line(
                    is_opening=False, player=player, exhausted=conversation_ended
                )
                llm_available = False
                logger.warning("chat_respond using deterministic fallback response. npc=%s response_chars=%s", self.name, len(npc_response or ""))

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
                    logger.info("chat_respond fallback pool exhausted; forcing conversation_ended. npc=%s", self.name)

            # Apply the NPC's in-character reaction to Jean's reputation
            if not hasattr(player, "reputation"):
                player.reputation = {}
            old_reputation = player.reputation.get(self.name, 0)
            new_reputation = max(-100, min(100, old_reputation + reputation_delta))
            player.reputation[self.name] = new_reputation

            # Jean's options for the next round. Once loquacity is spent the
            # options are omitted so the NPC's own (lore- and context-aware) reply
            # stands as the graceful closing line, with nothing left to say back.
            # Resolved before the persist below (it used to come after) so the
            # state guard can review the line, the flavor, and the options in a
            # single pass — and, more importantly, so only guarded text is ever
            # written: _load_history_from_persistence feeds the saved rows
            # straight back to the model next round, and a persisted "here, take
            # this blade" would keep breeding offers for the rest of the
            # conversation. +1 on the turn number preserves the old value, which
            # was read after the persist appended this round's row.
            jean_options: List[Dict[str, str]] = []
            if not conversation_ended:
                turn_number = len(self._chat_history) + 1
                jean_options = self._resolve_jean_options(
                    turn, adapter, npc_response, turn_number
                )

            # Model output only — see chat_open for why authored fallback
            # lines are left alone.
            if turn is not None:
                npc_response, npc_flavor, jean_options = self._guard_turn(
                    adapter, system, npc_response, npc_flavor, jean_options
                )

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
            # conversation_count is bumped separately (_bump_conversation_count,
            # below) — _save_exchange_to_persistence has no counter logic of
            # its own to ride on.
            game_tick = getattr(getattr(player, "universe", None), "game_tick", 0) or 0
            chapter = self._get_chapter(player)
            self._save_exchange_to_persistence(
                player, npc_response, "", game_tick, chapter
            )
            self._bump_conversation_count(player)

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
            # Detail stays server-side (the logger call above); the client
            # never sees raw exception text, which can leak internals.
            logger.error("ConversationalNPCMixin.chat_respond error: %s", e, exc_info=True)
            return {"success": False, "error": "Conversation failed — try again."}

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
        # Generic fallback. crc32 (not the built-in hash()) because hash() is
        # salted per process — the "deterministic" pick would otherwise
        # change every restart.
        fallbacks = [
            "They're not in the mood to talk.",
            "A brief shake of the head.",
            "Not now.",
        ]
        idx = zlib.crc32(self.name.encode("utf-8")) % len(fallbacks)
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
        """Return fallback Jean options, cycling through pool.

        Returns copies (not the shared module-level dicts) so callers can
        never mutate the pool, and tolerates minimal test doubles that skip
        _init_chat_attrs (same rationale as _next_from_pool).
        """
        idx = getattr(self, "_chat_fallback_idx", 0)
        pool = _JEAN_FALLBACK_POOL[idx % len(_JEAN_FALLBACK_POOL)]
        self._chat_fallback_idx = idx + 1
        return [dict(o) for o in pool]
