"""
MynxLLMMixin — LLM-driven ambient behaviour for the Mynx NPC.

Mixed into Mynx (npc.py).  The Mynx class itself is responsible only for
__init__, the four player-facing action methods (talk, pet, play, interact),
and the combat no-op override.  All prompt-building, text sanitisation,
pronoun enforcement, and adapter management lives here.

Attributes expected on the host class (provided by Mynx.__init__):
    self.name               str
    self.pronouns           dict
    self.current_room       Room | None
    self._llm_adapter       object | None   (lazy-loaded)
    self._llm_last_response dict | None
    self._llm_history       list[dict]
    self._jean_advisor      dict | None     (lazy-loaded)
"""

import importlib.util
import json
import os
import random
import re
import time
from pathlib import Path


class MynxLLMMixin:
    """LLM-driven ambient behaviour mixin for the Mynx."""

    # ── Precompiled regex (class-level; shared across all instances) ───────────
    _re_whitespace = re.compile(r"\s+")
    _re_sentence_split = re.compile(r"[.!?]")
    _re_capitalized_token = re.compile(r"^[A-Z][A-Za-z\-']+$")
    _re_disallowed_name_token = re.compile(r"\b([A-Z][A-Za-z\-]+)('s)?\b")
    _re_self_actions = re.compile(
        r"\b(batting|pawing|swatting|tapping) at (?:{name}|{pronoun})\b",
        re.IGNORECASE,
    )
    _re_duplicate_pronoun_template = r"\b({p})\s+\1\b"
    _gendered_pronouns = re.compile(r"\b(he|him|his|she|her|hers)\b", re.IGNORECASE)

    # ── LLM history ────────────────────────────────────────────────────────────

    def _append_llm_history(self, prompt: str, response: str):
        """Append a normalised prompt/response pair; keep only the last 3 entries."""
        try:
            if not isinstance(prompt, str):
                prompt = str(prompt or "")
            if not isinstance(response, str):
                response = str(response or "")
            p = re.sub(r"\s+", " ", prompt).strip()[:200]
            r = re.sub(r"\s+", " ", response).strip()[:300]
            if not p and not r:
                return
            self._llm_history.append({"prompt": p, "response": r})
            if len(self._llm_history) > 3:
                self._llm_history = self._llm_history[-3:]
        except Exception:
            return

    # ── Jean advisor (player pronoun / personality config) ─────────────────────

    def _load_player_advisor(self):
        """Lazy-load Jean's advisor JSON (ai/player/jean.json). Returns dict or fallback."""
        if self._jean_advisor is not None:
            return self._jean_advisor
        try:
            root = Path(__file__).resolve().parent.parent
            jean_path = root / "ai" / "player" / "jean.json"
            if jean_path.exists():
                with open(jean_path, "r", encoding="utf-8") as f:
                    self._jean_advisor = json.load(f)
            else:
                self._jean_advisor = {
                    "character_name": "Jean",
                    "pronouns": {
                        "subject": "he",
                        "object": "him",
                        "possessive_adjective": "his",
                    },
                    "system_prompt_snippet": (
                        "Jean is the human player (he/him). "
                        "Keep references to him concise and third-person."
                    ),
                }
        except Exception:
            self._jean_advisor = {
                "character_name": "Jean",
                "pronouns": {
                    "subject": "he",
                    "object": "him",
                    "possessive_adjective": "his",
                },
                "system_prompt_snippet": "Jean is the human player (he/him). Keep references concise.",
            }
        return self._jean_advisor

    # ── LLM adapter (lazy-loaded via importlib) ────────────────────────────────

    def _get_llm_adapter(self):
        """Return a live MynxLLMAdapter, or None if LLM is disabled / unavailable."""
        if self._llm_adapter is not None:
            return self._llm_adapter
        _debug = os.getenv("MYNX_LLM_DEBUG", "0") in ("1", "true", "True")
        if os.getenv("MYNX_LLM_ENABLED", "0") not in ("1", "true", "True"):
            self._llm_adapter = None
            if _debug:
                print(
                    "[MYNX_LLM_DEBUG] Adapter disabled: set MYNX_LLM_ENABLED=1 to enable."
                )
            return None
        try:
            root = Path(__file__).resolve().parent.parent
            adapter_path = root / "ai" / "llm_client.py"
            if not adapter_path.exists():
                self._llm_adapter = None
                if _debug:
                    print(
                        f"[MYNX_LLM_DEBUG] llm_client.py not found at {adapter_path}."
                    )
                return None
            spec = importlib.util.spec_from_file_location(
                "ai.llm_client", str(adapter_path)
            )
            if not (spec and spec.loader):
                self._llm_adapter = None
                if _debug:
                    print(
                        "[MYNX_LLM_DEBUG] Failed to create module spec for llm_client."
                    )
                return None
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            Adapter = getattr(mod, "MynxLLMAdapter", None)
            if Adapter is None:
                self._llm_adapter = None
                if _debug:
                    print(
                        "[MYNX_LLM_DEBUG] MynxLLMAdapter class not found in llm_client module."
                    )
                return None
            inst = Adapter()
            try:
                avail = inst.available()
            except Exception as e:
                avail = False
                if _debug:
                    print(f"[MYNX_LLM_DEBUG] Exception checking availability: {e}")
            if avail is True:
                self._llm_adapter = inst
                if _debug:
                    status = (
                        inst.debug_status() if hasattr(inst, "debug_status") else "ok"
                    )
                    print(f"[MYNX_LLM_DEBUG] Adapter available: {status}")
            else:
                if _debug and hasattr(inst, "debug_status"):
                    try:
                        print(
                            f"[MYNX_LLM_DEBUG] Adapter unavailable: {inst.debug_status()}"
                        )
                    except Exception:
                        pass
                self._llm_adapter = None
        except Exception as e:
            self._llm_adapter = None
            if _debug:
                print(f"[MYNX_LLM_DEBUG] Exception loading adapter: {e}")
        return self._llm_adapter

    # ── Text sanitisation ──────────────────────────────────────────────────────

    def _sanitize_mynx_llm_text(self, text: str, allowed_names) -> str:
        """Post-process LLM output to reduce self-referential confusion.

        Rules applied in order:
        - Normalise whitespace.
        - Replace all but the first occurrence of the mynx's own name with its pronoun.
        - Remove self-targeting action phrases (e.g. "batting at <name>").
        - Replace disallowed capitalised tokens with the appropriate pronoun.
        - Preserve possessives of allowed names; replace disallowed possessives with
          the possessive-adjective pronoun.
        - Collapse duplicate pronouns.
        """
        try:
            if not text:
                return text
            allowed = set(allowed_names or []) | {self.name, "Jean"}
            allowed_possessives = {f"{n}'s" for n in allowed}
            pronouns = self.pronouns if hasattr(self, "pronouns") else {}
            pronoun = pronouns.get("personal", "it")
            poss_adj = pronouns.get("possessive_adjective") or (
                "its" if pronoun == "it" else f"{pronoun}'s"
            )
            name = self.name

            text = re.sub(r"\s+", " ", text).strip()

            count = 0

            def repl_self(m):
                nonlocal count
                count += 1
                return name if count == 1 else pronoun

            text = re.compile(re.escape(name), re.IGNORECASE).sub(repl_self, text)
            text = re.sub(
                rf"\b(batting|pawing|swatting|tapping) at (?:{re.escape(name)}|{pronoun})\b",
                r"\1 playfully",
                text,
                flags=re.IGNORECASE,
            )

            cleaned = []
            for t in text.split(" "):
                if re.match(r"^[A-Z][A-Za-z\-']+$", t):
                    if t in allowed or t in allowed_possessives:
                        cleaned.append(t)
                    elif t.endswith("'s"):
                        base = t[:-2]
                        cleaned.append(t if base in allowed else poss_adj)
                    else:
                        cleaned.append(pronoun)
                else:
                    cleaned.append(t)
            text = " ".join(cleaned)
            text = re.sub(rf"\b({pronoun})\s+\1\b", pronoun, text, flags=re.IGNORECASE)
            return re.sub(r"\s+", " ", text).strip()
        except Exception:
            return text

    # ── Pronoun enforcement (post-sanitise pass) ───────────────────────────────

    def _enforce_pronouns_and_names(self, text: str, roster_set: set[str]) -> str:
        """Replace invented names and mismatched gendered pronouns with correct forms.

        Sentence-aware: sentences referencing Jean use Jean's pronouns; sentences
        referencing the mynx use its pronouns; all others use they/them/their.
        """
        try:
            if not text:
                return text
            pronouns = self.pronouns if hasattr(self, "pronouns") else {}
            pron_mynx = pronouns.get("personal", "it")
            poss_mynx = (
                pronouns.get("possessive_adjective")
                or pronouns.get("possessive")
                or "its"
            )
            allowed = roster_set | {self.name, "Jean"}

            def repl_name(m):
                base, possessive = m.group(1), m.group(2)
                if base in allowed:
                    return m.group(0)
                return pron_mynx + ("'s" if possessive else "")

            text = self._re_disallowed_name_token.sub(repl_name, text)

            jean_adv = self._load_player_advisor() or {}
            jean_pronouns = jean_adv.get("pronouns", {}) or {}
            jean_subj = jean_pronouns.get("subject", "he")
            jean_obj = jean_pronouns.get("object", "him")
            jean_poss = (
                jean_pronouns.get("possessive_adjective")
                or jean_pronouns.get("possessive")
                or "his"
            )

            def map_token(token, target):
                t = token.lower()
                if target == "jean":
                    return (
                        jean_subj
                        if t in ("he", "she")
                        else (
                            jean_obj
                            if t in ("him", "her")
                            else (jean_poss if t in ("his", "hers") else jean_subj)
                        )
                    )
                if target == "mynx":
                    return (
                        pron_mynx
                        if t in ("he", "she", "him", "her")
                        else (poss_mynx if t in ("his", "hers") else pron_mynx)
                    )
                return (
                    "they"
                    if t in ("he", "she")
                    else (
                        "them"
                        if t in ("him", "her")
                        else ("their" if t in ("his", "hers") else "they")
                    )
                )

            parts, last_end = [], 0
            for sep in re.finditer(r"[.!?]+", text):
                parts.append(text[last_end : sep.end()])
                last_end = sep.end()
            if last_end < len(text):
                parts.append(text[last_end:])

            processed = []
            for sent in parts:
                lowered = sent.lower()
                if "jean" in lowered:
                    target = "jean"
                elif self.name.lower() in lowered:
                    target = "mynx"
                else:
                    target = "neutral"

                def repl_gendered(m, _target=target):
                    return map_token(m.group(1), _target)

                processed.append(self._gendered_pronouns.sub(repl_gendered, sent))

            text = "".join(processed)
            dup_re = re.compile(
                self._re_duplicate_pronoun_template.format(p=re.escape(pron_mynx)),
                re.IGNORECASE,
            )
            return self._normalize_ws(dup_re.sub(pron_mynx, text))
        except Exception:
            return text

    # ── Context / prompt builders ──────────────────────────────────────────────

    def _gather_environment_lists(self):
        """Build a descriptive string of nearby items, objects, and NPCs for the LLM prompt.

        Returns a tuple of (env_string, empty_set).  The set is a legacy stub kept
        for call-site compatibility; callers should ignore it.
        """
        nearby_items, nearby_objects, other_npcs = [], [], []
        room = getattr(self, "current_room", None)
        if not room:
            return "", set()
        try:
            room_items = (
                getattr(room, "items_here", None)
                or getattr(room, "items", None)
                or getattr(room, "spawned", None)
                or []
            )
            for itm in room_items:
                nm = getattr(itm, "name", None) or getattr(itm, "title", None)
                desc = getattr(itm, "description", None) or getattr(
                    itm, "short_description", None
                )
                if isinstance(nm, str) and nm.strip():
                    entry = self._normalize_ws(nm)[:60]
                    if isinstance(desc, str) and desc.strip():
                        entry += f" — {self._normalize_ws(desc)[:140]}"
                    else:
                        entry += " — (no description)"
                    nearby_items.append(entry)
            room_objs = (
                getattr(room, "objects_here", None)
                or getattr(room, "objects", None)
                or []
            )
            for obj in room_objs:
                onm = getattr(obj, "name", None)
                odesc = getattr(obj, "description", None) or getattr(
                    obj, "summary", None
                )
                if isinstance(onm, str) and onm.strip():
                    entry = self._normalize_ws(onm)[:60]
                    if isinstance(odesc, str) and odesc.strip():
                        entry += f" — {self._normalize_ws(odesc).split('.')[0][:140]}"
                    else:
                        entry += " — (no description)"
                    nearby_objects.append(entry)
            for npc_inst in getattr(room, "npcs_here", []) or []:
                nm = getattr(npc_inst, "name", None)
                if isinstance(nm, str) and nm.strip() and nm != self.name:
                    ndesc = getattr(npc_inst, "description", None) or getattr(
                        npc_inst, "discovery_message", None
                    )
                    entry = self._normalize_ws(nm)[:60]
                    if isinstance(ndesc, str) and ndesc.strip():
                        entry += f" — {self._normalize_ws(ndesc)[:140]}"
                    else:
                        entry += " — (no description)"
                    other_npcs.append(entry)
        except Exception:
            pass

        def prep(lst):
            try:
                return "; ".join(list(dict.fromkeys(lst))[:5])
            except Exception:
                return ""

        env_parts = []
        ni, no, nn = prep(nearby_items), prep(nearby_objects), prep(other_npcs)
        if ni:
            env_parts.append(f"Nearby items (name — description): {ni}.")
        if no:
            env_parts.append(f"Nearby objects (name — description): {no}.")
        if nn:
            env_parts.append(f"Other nearby NPCs (name — description): {nn}.")
        return (" " + " ".join(env_parts) if env_parts else ""), set()

    def _build_history_block(self):
        """Serialise recent LLM history into a prompt fragment."""
        history_lines = []
        try:
            for h in (self._llm_history or [])[-3:]:
                phs = self._normalize_ws(str(h.get("prompt", "")))[:120]
                rhs = self._normalize_ws(str(h.get("response", "")))[:180]
                if phs or rhs:
                    history_lines.append(f"Prompt: '{phs}' -> Resp: '{rhs}'")
        except Exception:
            pass
        if history_lines:
            return (
                " Conversation history (most recent last): "
                + " | ".join(history_lines)
                + "."
            )
        return ""

    def _build_pronoun_guidance(self, jean_pronoun_line: str, jean_snippet: str) -> str:
        """Return the pronoun-guidance sentence for inclusion in the LLM context."""
        pronouns = self.pronouns if hasattr(self, "pronouns") else {}
        mynx_personal = pronouns.get("personal", "it")
        mynx_possessive = (
            pronouns.get("possessive_adjective") or pronouns.get("possessive") or "its"
        )
        try:
            pg = []
            if jean_pronoun_line:
                pg.append(f"For Jean use: {jean_pronoun_line.strip()}")
            pg.append(f"For the mynx use: {mynx_personal}/{mynx_possessive}.")
            pg.append(
                "For any other nearby NPCs, prefer using their NAME; if a pronoun is needed, use they/them/their."
            )
            return (" ".join(pg) + f" {jean_snippet}") if jean_snippet else " ".join(pg)
        except Exception:
            return "Use Jean and Mynx pronouns consistently; prefer names for others or they/them."

    def _build_llm_context(
        self,
        roster_set: set[str],
        prompt: str,
        jean_pronoun_line: str,
        jean_snippet: str,
    ) -> str:
        """Assemble the full context string to send to the LLM."""
        room_desc_raw = (
            getattr(self.current_room, "description", "")
            if getattr(self, "current_room", None)
            else ""
        )
        room_desc_raw = self._normalize_ws(room_desc_raw)
        room_desc = f" You are in {room_desc_raw}." if room_desc_raw else "."
        env_lists, _ = self._gather_environment_lists()
        history_block = self._build_history_block()
        pronoun_guidance = self._build_pronoun_guidance(jean_pronoun_line, jean_snippet)
        allowed_names = ", ".join(sorted(roster_set | {"Jean"}))
        parts = [
            "You describe only what the mynx does in one immediate, nonverbal action.",
            f"The mynx's proper name is {self.name}.",
            f"{self.name} is the ACTOR, never its own target.",
            f"Allowed entity names you may reference (no others): {allowed_names}.",
            "Do not invent other creature names. If the player is referenced use 'Jean'.",
            pronoun_guidance,
            "Keep it present-tense, concise (<=2 short sentences), no speech.",
            f"Player action/intent: '{prompt or 'interact'}'.",
            room_desc + env_lists,
            "Respond in a way that's appropriate for the environment.",
            history_block,
            "Try not to repeat recent actions or descriptions; be novel relative to the above history.",
        ]
        ctx = " ".join(filter(None, parts))
        if os.getenv("MYNX_LLM_DEBUG", "0") in ("1", "true", "True"):
            try:
                print(
                    f"[MYNX_LLM_DEBUG] Built context ({len(ctx)} chars): {ctx[:4000]}"
                )
            except Exception:
                pass
        return ctx

    # ── LLM output validation ──────────────────────────────────────────────────

    def _check_and_correct_mynx_text(
        self, text: str, prompt: str, roster
    ) -> str | None:
        """Validate and lightly correct LLM output.

        Returns the corrected text, or None if the output is unacceptable.

        Checks (in order):
        - Must be a non-empty string.
        - Must not contain quoted speech.
        - Trimmed to 2 sentences maximum.
        - Disallowed capitalised tokens replaced with pronouns.
        - Rejected if past-tense tokens dominate (>40 % and >3 tokens ending 'ed').
        - Length must be 5–200 chars.
        - Ensures terminal period.
        """
        try:
            if not isinstance(text, str):
                return None
            raw = text.strip()
            if not raw:
                return None
            if '"' in raw or ("'" in raw and (" says " in raw or raw.count('"') >= 2)):
                return None
            sentences = [s.strip() for s in re.split(r"[.!?]", raw) if s.strip()]
            if not sentences:
                return None
            candidate = ". ".join(sentences[:2])
            allowed = set(roster or []) | {self.name, "Jean"}
            pronouns = self.pronouns if hasattr(self, "pronouns") else {}
            pronoun = pronouns.get("personal", "it")
            poss_adj = (
                pronouns.get("possessive_adjective")
                or pronouns.get("possessive")
                or "its"
            )
            pattern = re.compile(r"\b([A-Z][A-Za-z\-]+)('s)?\b")

            def fix_token(m):
                base, possessive = m.group(1), m.group(2)
                if base in allowed:
                    return base + (possessive or "")
                return poss_adj if possessive else pronoun

            candidate = pattern.sub(fix_token, candidate)
            words = candidate.split()
            ed_tokens = [t for t in words if t.lower().endswith("ed")]
            if len(ed_tokens) > 3 and len(ed_tokens) >= len(words) * 0.4:
                return None
            candidate = candidate.strip()
            if not (5 <= len(candidate) <= 200):
                return None
            if not candidate.endswith("."):
                candidate += "."
            return candidate
        except Exception:
            return None

    # ── Core interaction entry-point ───────────────────────────────────────────

    def interact_with_player(
        self, player, prompt: str | None = None, structured: bool = False
    ):
        """Generate and display a mynx reaction to a player action.

        Attempts LLM generation when the adapter is available; falls back to
        deterministic canned responses for offline mode / tests.

        Args:
            player: The Player instance.
            prompt: Short description of the player's action (e.g. "pet", "feed").
            structured: If True, return a structured dict instead of a plain string.
        """
        _debug = os.getenv("MYNX_LLM_DEBUG", "0") in ("1", "true", "True")
        p = (prompt or "").strip().lower()

        # Print the player's side of the interaction
        if p in ("pet", "stroke", "scritch"):
            action_print = "Jean reaches out to pet the mynx."
        elif p in ("feed", "offer food", "give food"):
            action_print = "Jean offers a morsel of food to the mynx."
        elif p.startswith("play with ") or p in ("play", "toy", "tease"):
            item_name = (
                p[len("play with ") :].strip() if p.startswith("play with ") else None
            )
            action_print = (
                f"Jean plays with the mynx using {item_name}."
                if item_name
                else "Jean tries to play with the mynx."
            )
        elif p:
            action_print = f"Jean {p}."
        else:
            action_print = "Jean interacts with the mynx."
        try:
            print(action_print)
        except Exception:
            pass

        # Build roster of known NPC names in the room
        roster = []
        if getattr(self, "current_room", None) is not None:
            try:
                for npc_inst in getattr(self.current_room, "npcs_here", []) or []:
                    nm = getattr(npc_inst, "name", None)
                    if isinstance(nm, str):
                        roster.append(nm)
            except Exception:
                pass
        if self.name not in roster:
            roster.append(self.name)
        roster_set = set(roster)

        adapter = self._get_llm_adapter()
        if adapter is not None:
            jean_adv = self._load_player_advisor() or {}
            jean_pronouns = jean_adv.get("pronouns", {})
            jean_snippet = jean_adv.get("system_prompt_snippet", "")[:300]
            jean_pronoun_line = ""
            if jean_pronouns:
                subj = jean_pronouns.get("subject", "he")
                obj = jean_pronouns.get("object", "him")
                poss = jean_pronouns.get("possessive_adjective", "his")
                jean_pronoun_line = f"{subj}/{obj}/{poss}."
            context = self._build_llm_context(
                roster_set, p, jean_pronoun_line, jean_snippet
            )
            try:
                if structured:
                    result = adapter.generate_structured(context=context)
                    if isinstance(result, dict) and isinstance(
                        result.get("description"), str
                    ):
                        if _debug:
                            try:
                                print(
                                    f"[MYNX_LLM_DEBUG] Raw structured description: {result.get('description')}"
                                )
                            except Exception:
                                pass
                        desc = self._sanitize_mynx_llm_text(
                            result["description"], roster_set
                        )
                        desc = self._enforce_pronouns_and_names(desc, roster_set)
                        desc_checked = self._check_and_correct_mynx_text(
                            desc, p, roster
                        )
                        if desc_checked is not None:
                            result["description"] = desc_checked
                            self._llm_last_response = result
                            try:
                                self._append_llm_history(p, desc_checked)
                            except Exception:
                                pass
                            return result
                else:
                    text_resp = adapter.generate_plain(context=context)
                    if isinstance(text_resp, str) and text_resp:
                        if _debug:
                            try:
                                print(f"[MYNX_LLM_DEBUG] Raw plain text: {text_resp}")
                            except Exception:
                                pass
                        sanitized = self._sanitize_mynx_llm_text(text_resp, roster_set)
                        sanitized = self._enforce_pronouns_and_names(
                            sanitized, roster_set
                        )
                        checked = self._check_and_correct_mynx_text(
                            sanitized, p, roster
                        )
                        if checked is not None:
                            self._llm_last_response = {
                                "action": "narrate",
                                "intensity": "low",
                                "description": checked,
                                "duration_seconds": 2,
                                "audible": "soft chitter",
                            }
                            try:
                                self._append_llm_history(p, checked)
                            except Exception:
                                pass
                            print(checked)
                            return checked
            except Exception as e:
                if _debug:
                    print(
                        f"[MYNX_LLM_DEBUG] Generation/validation error, falling back: {e}"
                    )

        # ── Deterministic fallback (offline / test mode) ───────────────────────
        if p in ("pet", "stroke", "scritch"):
            variations = [
                f"{self.name} leans into the hand, purring a soft chitter and nudging the wrist with its head.",
                f"{self.name} rolls onto its back, exposing its belly and chirruping happily as you scritch it.",
                f"{self.name} closes its eyes, leaning heavily into your palm with a contented rumble.",
                f"{self.name} brushes its cheek against your fingers, its tail curling around your wrist affectionately.",
            ]
            text = random.choice(variations)
            structured_obj = {
                "action": "groom",
                "intensity": "gentle",
                "description": text,
                "duration_seconds": 2,
                "audible": "soft purr/chitter",
            }
        elif p in ("feed", "offer food", "give food"):
            variations = [
                f"{self.name} eyes the offered morsel, snatches it with a quick paw, and tucks it into its tail-fur triumphantly.",
                f"{self.name} sniffs the food cautiously, then delicately takes it from your hand, chittering a thank-you.",
                f"{self.name} pounces on the snack, carrying it a few paces away to gobble it down with happy chirps.",
                f"{self.name} stands on its hind legs to reach the food, batting at it playfully before taking a nibble.",
            ]
            text = random.choice(variations)
            structured_obj = {
                "action": "take_food",
                "intensity": "medium",
                "description": text,
                "duration_seconds": 3,
                "audible": "happy chitter",
            }
        elif p in ("play", "toy", "tease"):
            variations = [
                f"{self.name} bats the object with nimble paws, then darts back and forth in a brief, jubilant display.",
                f"{self.name} crouches low, tail twitching, then pounces at the object with a playful yip.",
                f"{self.name} stands on its hind legs, swatting at the air as if chasing an invisible butterfly.",
                f"{self.name} circles you rapidly, occasionally stopping to tap your boot before darting away.",
            ]
            text = random.choice(variations)
            structured_obj = {
                "action": "play",
                "intensity": "high",
                "description": text,
                "duration_seconds": 4,
                "audible": "rapid chitters",
            }
        else:
            variations = [
                f"{self.name} pads forward on silent paws, head cocked, whiskers twitching as it studies you.",
                f"{self.name} tilts its head, watching your every move with bright, intelligent eyes.",
                f"{self.name} flickers its tufted tail, chapping its teeth together in a curious greeting.",
                f"{self.name} sits back on its haunches, grooming its spotted fur while keeping one eye on you.",
            ]
            text = random.choice(variations)
            structured_obj = {
                "action": "investigate",
                "intensity": "low",
                "description": text,
                "duration_seconds": 3,
                "audible": "soft chitter",
            }

        try:
            self._append_llm_history(p, text)
        except Exception:
            pass
        self._llm_last_response = structured_obj
        if structured:
            return structured_obj
        print(text)
        try:
            delay = float(os.getenv("MYNX_FALLBACK_DELAY", "1.5"))
        except Exception:
            delay = 1.5
        if delay > 0:
            try:
                time.sleep(delay)
            except Exception:
                pass
        return text

    # ── Utilities ──────────────────────────────────────────────────────────────

    def _normalize_ws(self, text: str) -> str:
        """Collapse whitespace and strip leading/trailing spaces."""
        try:
            return self._re_whitespace.sub(" ", text).strip()
        except Exception:
            return text.strip() if isinstance(text, str) else str(text)
