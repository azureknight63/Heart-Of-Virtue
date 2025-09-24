import json
import os
from typing import Any, Dict, Optional

# We intentionally import requests lazily inside provider code paths so tests don't require it

AI_DIR = os.path.dirname(__file__)
MYNX_JSON_PATH = os.path.join(AI_DIR, "npc", "animal", "mynx.json")


class _JSONTools:
    @staticmethod
    def try_parse_json(s: str) -> Optional[Dict[str, Any]]:
        s = s.strip()
        # Quick guard: trim code fences if present
        if s.startswith("```"):
            # remove first fence line
            s = "\n".join(line for line in s.splitlines() if not line.strip().startswith("```") )
            s = s.strip()
        # Attempt direct parse
        try:
            return json.loads(s)
        except Exception:
            pass
        # Heuristic: extract the first {...} block
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and start < end:
            frag = s[start : end + 1]
            try:
                return json.loads(frag)
            except Exception:
                return None
        return None

    @staticmethod
    def sanitize_text(text: str) -> str:
        # Remove surrounding quotes if present and collapse whitespace
        t = text.strip()
        if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
            t = t[1:-1].strip()
        # Keep it short-ish
        t = " ".join(t.split())
        return t[:500]


class MynxLLMAdapter:
    """Adapter for generating Mynx responses using either a local Ollama model or an OpenRouter API model.

    Providers:
      - ollama      (local inference)
      - openrouter  (remote via OpenRouter API compatible w/ OpenAI SDK)

    Common Env configuration:
      - MYNX_LLM_ENABLED=1                  -> enable calling an LLM provider
      - MYNX_LLM_PROVIDER=ollama|openrouter -> provider type (default 'ollama')
      - MYNX_LLM_MODEL=<model_id>           -> model name (ollama tag or openrouter model id)

    Provider-specific:
      Ollama:
        - MYNX_LLM_URL=http://localhost:11434  (optional override)
      OpenRouter:
        - OPENROUTER_API_KEY=... (required when provider=openrouter)
        - OPENROUTER_SITE=https://example.com (optional ranking metadata)
        - OPENROUTER_SITE_TITLE="Your Site"   (optional ranking metadata)

    Defaults:
      - model: 'llama3.1:7b' for ollama, 'x-ai/grok-4-fast:free' for openrouter (if unset)
    """

    def __init__(self):
        self.enabled = os.getenv("MYNX_LLM_ENABLED", "0") in ("1", "true", "True")
        self.provider = os.getenv("MYNX_LLM_PROVIDER", "").strip().lower() or "ollama"
        # Choose a sensible default model per provider if user did not specify
        default_model = "llama3.1:7b" if self.provider == "ollama" else "x-ai/grok-4-fast:free"
        self.model = os.getenv("MYNX_LLM_MODEL", "").strip() or default_model
        self.base_url = os.getenv("MYNX_LLM_URL", "").strip() or "http://localhost:11434"

        # OpenRouter specific configuration
        self._openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self._openrouter_site = os.getenv("OPENROUTER_SITE", "").strip() or None
        self._openrouter_site_title = os.getenv("OPENROUTER_SITE_TITLE", "").strip() or None

        self._advisor = self._load_mynx_advisor()
        self._allowed_actions = set(self._advisor.get("behavior_profile", {}).get("typical_actions", []))
        self._system_prompt = self._advisor.get("system_prompt_snippet", "")
        # Example schema for structured responses
        self._example_struct = self._advisor.get("example_structured_response", {})

        # Probe availability lazily; we don't want to fail import-time
        self._available: Optional[bool] = None

    def available(self) -> bool:
        if not self.enabled:
            return False
        if self._available is not None:
            return self._available
        if self.provider == "ollama":
            try:
                import requests  # type: ignore
                r = requests.get(self.base_url + "/api/tags", timeout=1.5)
                self._available = r.status_code == 200
            except Exception:
                self._available = False
            return self._available
        if self.provider == "openrouter":
            # Consider it available if API key present; we avoid a network probe to keep tests fast/offline-safe.
            self._available = bool(self._openrouter_api_key)
            return self._available
        # Unknown provider
        self._available = False
        return False

    def generate_plain(self, context: str) -> Optional[str]:
        if not self.available():
            return None
        if self.provider == "ollama":
            return self._ollama_chat(context=context, structured=False)
        if self.provider == "openrouter":
            return self._openrouter_chat(context=context, structured=False)
        return None

    def generate_structured(self, context: str) -> Optional[Dict[str, Any]]:
        if not self.available():
            return None
        if self.provider == "ollama":
            obj = self._ollama_chat(context=context, structured=True)
        elif self.provider == "openrouter":
            obj = self._openrouter_chat(context=context, structured=True)
        else:
            return None
        if isinstance(obj, dict):
            valid = self._validate_structured(obj)
            if valid:
                return obj
            # attempt a minimal repair: coerce action and description
            repaired = self._repair_structured(obj)
            if repaired and self._validate_structured(repaired):
                return repaired
        return None

    # Provider-specific implementation: Ollama (local)
    def _ollama_chat(self, context: str, structured: bool) -> Optional[Any]:
        import requests  # type: ignore
        url = self.base_url + "/api/chat"
        user_prompt = self._build_user_prompt(context=context, structured=structured)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            # Keep responses short and deterministic-ish
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "num_ctx": 2048,
            },
        }
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code != 200:
                return None
            # Robustly extract textual content from multiple possible Ollama response shapes
            content = None
            try:
                data = r.json()
            except Exception:
                data = None

            if isinstance(data, dict):
                # common shape: {"message": {"content": "..."}}
                msg = data.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content") or msg.get("text")
                # OpenAI-like choices
                if content is None and isinstance(data.get("choices"), list):
                    for c in data.get("choices"):
                        if isinstance(c, dict):
                            m = c.get("message")
                            if isinstance(m, dict) and (m.get("content") or m.get("text")):
                                content = m.get("content") or m.get("text")
                                break
                            if c.get("content") or c.get("text"):
                                content = c.get("content") or c.get("text")
                                break
                # Ollama sometimes returns 'output' array where elements have 'content' or 'text'
                if content is None and isinstance(data.get("output"), list):
                    parts = []
                    for el in data.get("output"):
                        if isinstance(el, dict):
                            parts.append(el.get("content") or el.get("text") or "")
                        elif isinstance(el, str):
                            parts.append(el)
                    content = "\n".join(p for p in parts if p)
                # Some versions use 'result' or top-level 'content'/'text'
                if content is None:
                    if isinstance(data.get("result"), str):
                        content = data.get("result")
                    elif isinstance(data.get("result"), dict):
                        content = data.get("result").get("content") or data.get("result").get("text")
                if content is None:
                    content = data.get("content") or data.get("text")
            # Fallback to raw text body
            if not content:
                raw = r.text or ""
                content = raw.strip()

            if structured:
                # Try parse JSON from content robustly
                obj = _JSONTools.try_parse_json(content)
                return obj
            # Plain text: sanitize and return short string
            return _JSONTools.sanitize_text(content or "")
        except Exception:
            return None

    # Provider-specific implementation: OpenRouter (remote API)
    def _openrouter_chat(self, context: str, structured: bool) -> Optional[Any]:
        try:
            # Import openai lazily so the dependency is optional when provider not in use
            from openai import OpenAI  # type: ignore
        except Exception:
            return None
        if not self._openrouter_api_key:
            return None
        user_prompt = self._build_user_prompt(context=context, structured=structured)
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self._openrouter_api_key)
        headers = {}
        if self._openrouter_site:
            headers["HTTP-Referer"] = self._openrouter_site
        if self._openrouter_site_title:
            headers["X-Title"] = self._openrouter_site_title
        try:
            completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                extra_headers=headers or None,
                temperature=0.2,
                top_p=0.9,
                # Provide a gentle max tokens guard (OpenRouter accepts OpenAI fields)
                max_tokens=256 if not structured else 180,
            )
        except Exception:
            return None
        # Extract first message content (OpenAI-compatible schema)
        try:
            msg = completion.choices[0].message  # type: ignore
            content = getattr(msg, "content", None)
            if not content and isinstance(msg, dict):
                content = msg.get("content")
        except Exception:
            content = None
        if not content:
            return None
        if structured:
            return _JSONTools.try_parse_json(str(content))
        return _JSONTools.sanitize_text(str(content))

    def _build_user_prompt(self, context: str, structured: bool) -> str:
        ctx = context.strip()
        if structured:
            allowed = ", ".join(sorted(self._allowed_actions)) or "investigate_object, groom, play"
            schema_hint = json.dumps(self._example_struct or {
                "action": "investigate_object",
                "intensity": "low",
                "description": "The mynx inspects the object.",
                "duration_seconds": 2,
                "audible": "soft chitter"
            })
            return (
                "Return exactly one JSON action object. "
                "Use this exact schema and keys; no extra fields. "
                f"Allowed actions: {allowed}. "
                "Do not include code fences or commentary. "
                f"Context: {ctx}. "
                f"Schema example: {schema_hint}"
            )
        else:
            return (
                "Return plain description. One immediate nonverbal action of the mynx, "
                "present-tense, <= 2 short sentences. No quotes, no speech. "
                f"Context: {ctx}"
            )

    def _validate_structured(self, obj: Dict[str, Any]) -> bool:
        # Minimal schema validation
        required = {"action", "intensity", "description", "duration_seconds", "audible"}
        if not required.issubset(obj.keys()):
            return False
        if not isinstance(obj.get("action"), str):
            return False
        if obj["action"] not in self._allowed_actions:
            return False
        if not isinstance(obj.get("description"), str):
            return False
        # keep description sanitized
        obj["description"] = _JSONTools.sanitize_text(obj["description"])  # type: ignore
        return True

    def _repair_structured(self, obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Coerce to expected keys and clamp action to first allowed
        action = obj.get("action")
        desc = obj.get("description") or obj.get("text") or ""
        if not isinstance(desc, str):
            desc = str(desc)
        desc = _JSONTools.sanitize_text(desc)
        # choose a default allowed action if invalid
        if not isinstance(action, str) or action not in self._allowed_actions:
            action = next(iter(self._allowed_actions)) if self._allowed_actions else "investigate_object"
        repaired = {
            "action": action,
            "intensity": obj.get("intensity") or "low",
            "description": desc,
            "duration_seconds": obj.get("duration_seconds") or 2,
            "audible": obj.get("audible") or "soft chitter",
        }
        return repaired

    def _load_mynx_advisor(self) -> Dict[str, Any]:
        try:
            with open(MYNX_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # Fallback minimal advisor
            return {
                "behavior_profile": {"typical_actions": ["investigate_object", "groom", "play"]},
                "system_prompt_snippet": (
                    "You are an assistant for an in-game creature called the mynx. "
                    "Only produce nonverbal action descriptions or compact JSON action objects."
                ),
            }
