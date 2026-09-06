"""Text and JSON munging for the LLM transports.

Split out of ``ai/llm_client.py``, which had grown to 4600 lines. This half is
the part with no state, no network and no configuration: everything here is a
pure function of a string a provider sent or a string about to be interpolated
into a prompt. It moved verbatim -- same names, same signatures, same bodies --
and ``ai/llm_client`` re-exports both, so nothing that imported them from there
had to change.

The one dependency worth naming is ``src.text_safety``: ``sanitize_text``
neutralises as it tidies, because every caller's output is either narrated to
the player or interpolated back into a prompt. See that module for why the
whitespace collapse alone was not enough.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from src.text_safety import neutralise_model_text


class _JSONTools:
    @staticmethod
    def strip_code_fences(s: str) -> str:
        """Remove markdown code fences around a response.

        Handles an opening fence with or without a language tag, content on
        the same line as either fence, and any stray fence-only lines.
        """
        s = s.strip()
        if not s.startswith("```"):
            return s
        s = re.sub(r"^```[A-Za-z0-9_-]*[ \t]*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
        s = "\n".join(line for line in s.splitlines() if line.strip() != "```")
        return s.strip()

    @staticmethod
    def _keep_first_duplicate(
        pairs: List[Tuple[str, Any]]
    ) -> Dict[str, Any]:
        """object_pairs_hook that keeps the FIRST value for a repeated key.

        json.loads keeps the last by default, which is exactly wrong for the way
        models fail: they emit a good object, close it, then append a degenerate
        afterthought. Observed live from a free model that produced three usable
        jean_options and then a second, empty ``jean_options`` — last-wins turned
        that into zero options, parsed cleanly, with nothing in the logs.
        """
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key not in result:
                result[key] = value
        return result

    @staticmethod
    def try_parse_json(s: str) -> Optional[Any]:
        """Best-effort JSON parse of a model response.

        Returns whatever ``json.loads`` yields for the matched fragment (a
        dict for the common case, but a list/str/number/bool/None is legal
        JSON too) — callers must isinstance-check before treating the result
        as a mapping.
        """
        s = _JSONTools.strip_code_fences(s)
        # Attempt direct parse
        try:
            return json.loads(s, object_pairs_hook=_JSONTools._keep_first_duplicate)
        except Exception:
            pass
        # Heuristic: extract the first {...} block
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and start < end:
            frag = s[start:end + 1]
            try:
                return json.loads(
                    frag, object_pairs_hook=_JSONTools._keep_first_duplicate
                )
            except Exception:
                pass
        # Last resort: the response may be a JSON object cut off mid-generation
        # (max_tokens exhausted) — salvage the complete leading fields.
        return _JSONTools._repair_truncated_json(s)

    @staticmethod
    def extract_json_list(raw: str) -> Optional[List[Any]]:
        """Pull a JSON array out of a model reply, whatever it wrapped it in.

        Three shapes reach this, and every one of them is something a real free
        model has answered with when asked for a list:

        * ``{"options": [...]}`` — a model honouring JSON mode, which forbids a
          top-level array;
        * a bare ``[...]`` — a model ignoring it;
        * prose with either embedded in it.

        Objects go through ``try_parse_json`` so they get the shared salvage
        stack (fragment extraction, truncated-JSON repair, the keep-first hook);
        the bare-array case gets its own bracket extraction, which that
        dict-focused stack does not cover. Returns None when nothing usable is
        in there.

        Lives here rather than inline in ``generate_jean_options`` because it is
        salvage, and every other piece of the salvage stack is on this class.
        """
        raw = _JSONTools.strip_code_fences(raw or "")
        parsed: Any = _JSONTools.try_parse_json(raw)
        if isinstance(parsed, dict) and not any(
            isinstance(v, list) for v in parsed.values()
        ):
            # try_parse_json's fragment extraction can grab one inner object out
            # of a prose-wrapped ARRAY; with no list value it is not the wrapper,
            # so fall through to bracket extraction.
            parsed = None
        if parsed is None:
            start, end = raw.find("["), raw.rfind("]")
            if start != -1 and end > start:
                try:
                    parsed = json.loads(
                        raw[start:end + 1],
                        object_pairs_hook=_JSONTools._keep_first_duplicate,
                    )
                except Exception:
                    parsed = None
        if isinstance(parsed, dict):
            # e.g. {"options": [...]} — take the first list the wrapper holds.
            parsed = next(
                (v for v in parsed.values() if isinstance(v, list)), None
            )
        return parsed if isinstance(parsed, list) else None

    @staticmethod
    def _repair_truncated_json(s: str) -> Optional[Dict[str, Any]]:
        """Best-effort salvage of a JSON object cut off mid-generation.

        A response truncated by the token cap has no closing brace, so both the
        direct parse and the ``{...}`` extraction fail and the entire payload —
        including fields that arrived intact — used to be discarded. This drops
        the trailing partial member, appends the missing closers, and retries;
        on failure it chops back to the previous comma and tries again a few
        times.

        DROP THE INCOMPLETE MEMBER FIRST; close an unterminated string only
        when there is nothing left to drop. The order is the whole point. This
        used to append the missing ``"`` before anything else, which *keeps*
        the member the token cap cut in half: a reply truncated inside a
        ``"text"`` value came back as
        ``{"tone": "direct", "text": "Ask her how deep the ford ru"}`` — a
        mid-word amputation that is under ``MAX_OPTION_CHARS``, over
        ``_MIN_OPTION_CHARS`` and matches no meta pattern, so
        ``_clean_jean_options`` and ``_qc_jean_options`` both waved it through
        and the player was offered it as a button. ``_clean_option_text`` trims
        an over-long option back to a word boundary and ``_qc_jean_options``
        drops one it cannot trim precisely so that this never ships; salvage
        had been quietly manufacturing the thing they exist to prevent.

        Chopping to the last comma OUTSIDE a string, not the last comma
        anywhere: a comma inside the unterminated value is not a member
        boundary, and cutting there left the fragment in place (one word
        shorter) for the next pass to close.

        The close-the-string last resort remains for the case with no member
        to drop — a single-field reply such as ``{"description": "half a li``,
        where the alternative is discarding the answer entirely.
        """
        start = s.find("{")
        if start == -1:
            return None
        candidate = s[start:]
        for _ in range(6):
            stack: List[str] = []
            in_str = False
            esc = False
            last_comma = -1
            for i, ch in enumerate(candidate):
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                elif ch == '"':
                    in_str = True
                elif ch in "{[":
                    stack.append(ch)
                elif ch in "}]" and stack:
                    stack.pop()
                elif ch == ",":
                    last_comma = i
            if in_str and last_comma > 0:
                # Truncated mid-string with an earlier member to fall back on:
                # drop the fragment rather than closing a quote around it.
                candidate = candidate[:last_comma]
                continue
            attempt = candidate + ('"' if in_str else "")
            attempt = re.sub(r"[,\s]+$", "", attempt)
            attempt = re.sub(r'"[^"]*"\s*:\s*$', "", attempt)  # dangling key
            attempt = re.sub(r"[,\s]+$", "", attempt)
            attempt += "".join("}" if c == "{" else "]" for c in reversed(stack))
            try:
                parsed = json.loads(
                    attempt, object_pairs_hook=_JSONTools._keep_first_duplicate
                )
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                cut = last_comma
                if cut <= 0:
                    return None
                candidate = candidate[:cut]
        return None

    @staticmethod
    def extract_text_content(content) -> Optional[str]:
        """Extract text-only content from a response that may contain thinking blocks.

        OpenRouter thinking-mode models return content as a list of blocks:
          [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "..."}]
        This helper extracts only the text blocks and ignores thinking blocks.
        """
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "thinking":
                        continue  # skip thinking tokens
                    text = block.get("text") or block.get("content") or ""
                    if text:
                        parts.append(str(text))
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(parts) if parts else None
        return str(content) if content else None

    @staticmethod
    def extract_message_text(message: Optional[dict]) -> Optional[str]:
        """Normalize one chat-completion message into plain response text.

        Different providers (and Ollama itself) shape "the answer" differently:
        a plain string ``content``, a list of content blocks mixing thinking
        and text, or — when a reasoning model burns its token budget before
        finishing — an empty ``content`` with the chain-of-thought sitting in
        a separate field instead (``reasoning`` / ``reasoning_details`` on
        OpenRouter, ``thinking`` on Ollama). This is the single place that
        reconciles those shapes into one string (or None) before any caller
        hands it to ``try_parse_json``, so the parser always sees the same
        normalized input regardless of which model answered.
        """
        if not isinstance(message, dict):
            return None

        text = _JSONTools.extract_text_content(message.get("content"))
        if not text:
            # Some completion-style responses use "text" instead of "content".
            text = _JSONTools.extract_text_content(message.get("text"))
        if text and text.strip():
            # Strip *before* deciding, not after: content that is nothing but
            # an unclosed <think> block strips to "", and returning that here
            # made the reasoning/thinking fallbacks below unreachable. ""
            # is not None, so callers skipped their own salvage branches too
            # and the turn was discarded with its answer sitting in `reasoning`.
            stripped = _JSONTools._strip_thinking_tokens(text)
            if stripped and stripped.strip():
                return stripped

        # content was empty/null — the model likely spent its budget on
        # reasoning without producing a final answer. Chain-of-thought is not
        # the answer, but on some free models it's the only thing that comes
        # back, so treat it as a last resort rather than giving up outright.
        for key in ("reasoning", "thinking"):
            fallback = message.get(key)
            if isinstance(fallback, str) and fallback.strip():
                return _JSONTools._strip_thinking_tokens(fallback)

        details = message.get("reasoning_details")
        if isinstance(details, list):
            parts = [
                str(d["text"]) for d in details
                if isinstance(d, dict) and d.get("text")
            ]
            if parts:
                return _JSONTools._strip_thinking_tokens("\n".join(parts))

        return None

    @staticmethod
    def _strip_thinking_tokens(text: str) -> str:
        """Strip chain-of-thought tokens from models that wrap reasoning in XML-like tags.

        Handles:
          - ``<think>...</think>`` / ``<thinking>...</thinking>`` blocks anywhere
          - Any unmatched ``<think>`` opener, wherever it appears — everything
            from the opener to the end is chain-of-thought the model never
            closed (token budget ran out), so it is dropped rather than leaked
        """
        # Drop any matched thinking blocks, including multiline
        text = re.sub(
            r"<think(?:ing)?>.*?</think(?:ing)?>", "", text,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Any opener still present is unmatched; drop from there to the end so
        # reasoning never leaks into JSON parsing or player-visible text. (An
        # opener at position 0 therefore yields "" and the caller falls back.)
        m = re.search(r"<think(?:ing)?>", text, flags=re.IGNORECASE)
        if m:
            text = text[: m.start()]

        # Collapse residual blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def sanitize_text(text: str) -> str:
        """Tidy one model-authored string for storage, prompts, and display.

        Un-quotes, neutralises, bounds. The neutralisation is not decorative:
        every caller's output ends up either narrated to a player-visible
        renderer or interpolated back into a prompt, and this used to collapse
        whitespace with ``" ".join(split())`` — which leaves ``\\x1b``,
        ``\\x00-\\x08`` and ``\\x7f`` exactly where they were. ``npc_text``
        carrying a live ANSI escape is a colour change the game did not ask
        for; ``npc_flavor`` carrying a ``</player_input>`` is a prompt fence
        the model can close for free.

        ``neutralise_model_text`` also subsumes the whitespace collapse, so
        the two spellings of "collapse whitespace" that used to sit either
        side of this boundary are now one.
        """
        # Remove surrounding quotes if present
        t = text.strip()
        if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
            t = t[1:-1].strip()
        # Keep it short-ish
        return neutralise_model_text(t)[:500]


def _quote_for_prompt(text: Any) -> str:
    """Escape text that is about to be interpolated inside a quoted span.

    ``neutralise_model_text`` removes the fence tag and every line break, so
    what is left that can forge structure is the delimiter the *caller* chose.
    A prompt line reading ``Bob just said: "<value>"`` ends at the first double
    quote inside ``<value>``, and everything after it reads as prose the prompt
    itself wrote — which is instruction position by another name.

    Backslash first, then the quote, in that order: escaping the quote first
    would leave the backslash it introduced open to being escaped again. The
    result is what every model already reads as an escaped quote.

    Not folded into ``neutralise_model_text``: that function is about what the
    *text* may contain, this is about the syntax of one call site. A caller
    that fences instead of quoting needs neither.
    """
    return str(text).replace("\\", "\\\\").replace('"', '\\"')
