import json
import os
import logging
from typing import Any, Dict, Optional, List
import requests
from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv()

# We intentionally import requests lazily inside provider code paths so tests don't require it

AI_DIR = os.path.dirname(__file__)
MYNX_JSON_PATH = os.path.join(AI_DIR, "npc", "animal", "mynx.json")


logger = logging.getLogger(__name__)

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


class GenericLLMClient:
    """Adapter for generating responses using either a local Ollama model or an OpenRouter API model.

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
      - model: 'llama3.1:7b' for ollama, 'google/gemini-flash-1.5:free' for openrouter (if unset)
    """

    def __init__(self):
        self.enabled = os.getenv("MYNX_LLM_ENABLED", "0") in ("1", "true", "True")
        self.provider = os.getenv("MYNX_LLM_PROVIDER", "").strip().lower() or "ollama"
        # Choose a sensible default model per provider if user did not specify
        default_model = "llama3.1:7b" if self.provider == "ollama" else "google/gemini-flash-1.5:free"
        self.model = os.getenv("MYNX_LLM_MODEL", "").strip() or "auto"
        logger.info(f"DEBUG: Initializing GenericLLMClient (Provider: {self.provider}, Model: {self.model}, Enabled: {self.enabled})")
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()

        # OpenRouter specific configuration
        self._openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self._openrouter_site = os.getenv("OPENROUTER_SITE", "").strip() or None
        self._openrouter_site_title = os.getenv("OPENROUTER_SITE_TITLE", "").strip() or None
        self._free_models_cache: List[str] = []
        self._failed_models = set() # Track models that failed during this session

        # Probe availability lazily; we don't want to fail import-time
        self._available: Optional[bool] = None
        self._unavailable_reason: Optional[str] = None
        
        # Discover models
        if self.enabled:
            if self.provider == "ollama" and not os.getenv("MYNX_LLM_MODEL"):
                self._discover_ollama_model()
            elif self.provider == "openrouter":
                self._discover_openrouter_model()
                self._validate_and_fallback_openrouter()

    def _discover_ollama_model(self):
        """Try to find an available Ollama model if the default is missing."""
        try:
            import requests # type: ignore
            r = requests.get(self.base_url + "/api/tags", timeout=1.5)
            if r.status_code == 200:
                data = r.json()
                models = [m.get("name") for m in data.get("models", [])]
                if models and self.model not in models:
                    # Prefer gemma, then llama, then the first one available
                    for pref in ["gemma", "llama", "mistral", "phi"]:
                        for m in models:
                            if pref in m.lower():
                                self.model = m
                                return
                    self.model = models[0]
        except Exception:
            pass

    def _discover_openrouter_model(self):
        """Fetch list of free models from OpenRouter to use as fallbacks."""
        if not self._openrouter_api_key:
            return
        
        try:
            r = requests.get("https://openrouter.ai/api/v1/models", timeout=5)
            if r.status_code == 200:
                data = r.json()
                models = data.get("data", [])
                free_models = []
                for m in models:
                    pricing = m.get("pricing", {})
                    # Look for truly free models (0 cost for prompt and completion)
                    try:
                        p_val = float(pricing.get("prompt", 1))
                        c_val = float(pricing.get("completion", 1))
                        if p_val == 0 and c_val == 0:
                            free_models.append(m.get("id"))
                    except (ValueError, TypeError):
                        continue
                
                self._free_models_cache = free_models
                logger.info(f"DEBUG: Discovered {len(free_models)} free OpenRouter models.")
                
                # If current model is generic or unset, pick the best available free model
                if self.model in ["auto", "free", ""] or not self.model:
                    # Preference order for selection
                    prefs = ["llama-3.3-70b", "llama-3.2-3b", "mistral-small-3.1-24b", "gemini-2.0-flash-exp", "gemini-flash-1.5"]
                    selected = None
                    for pref in prefs:
                        for m_id in free_models:
                            if pref in m_id.lower():
                                selected = m_id
                                break
                        if selected: break
                    
                    self.model = selected or (free_models[0] if free_models else "meta-llama/llama-3.3-70b-instruct:free")
        except Exception as e:
            logger.warning(f"DEBUG: Failed to discover OpenRouter models: {e}")

    def _validate_and_fallback_openrouter(self):
        """Test the current model and fallback through others until one works."""
        if not self.enabled or not self._openrouter_api_key:
            return

        logger.info(f"DEBUG: Validating OpenRouter model: {self.model}")
        
        # We perform a tiny test chat to verify connectivity and availability
        def test_one(m_id):
            if m_id in self._failed_models: return False
            try:
                # Use internal chat with no fallback for the test itself
                res = self._openrouter_chat_single(m_id, "System", "Say OK", False)
                return res is not None and "ok" in str(res).lower()
            except Exception:
                return False

        if test_one(self.model):
            logger.info(f"DEBUG: Primary model {self.model} verified.")
            self._available = True
            return

        logger.warning(f"DEBUG: Primary model {self.model} failed. Searching for fallback...")
        self._failed_models.add(self.model)

        # Gather fallbacks
        candidates = []
        if self._free_models_cache:
            candidates.extend([m for m in self._free_models_cache if m != self.model])
        
        stable = [
            "meta-llama/llama-3.3-70b-instruct:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "google/gemini-flash-1.5:free"
        ]
        for s in stable:
            if s not in candidates and s != self.model:
                candidates.append(s)

        for cand in candidates:
            if cand in self._failed_models: continue
            logger.info(f"DEBUG: Testing fallback: {cand}")
            if test_one(cand):
                logger.info(f"DEBUG: Found working fallback: {cand}")
                self.model = cand
                self._available = True
                return
            else:
                self._failed_models.add(cand)

        logger.error("DEBUG: All OpenRouter models failed validation. Disabling LLM.")
        self._available = False
        self.enabled = False

    def available(self) -> bool:
        if not self.enabled:
            self._unavailable_reason = "Adapter disabled (set MYNX_LLM_ENABLED=1 to enable)."
            return False
        if self._available is not None:
            return self._available
        
        logger.info(f"DEBUG: Probing availability for {self.provider}")
        # Reset reason before probe
        self._unavailable_reason = None
        if self.provider == "ollama":
            try:
                import requests  # type: ignore
                r = requests.get(self.base_url + "/api/tags", timeout=1.5)
                if r.status_code == 200:
                    self._available = True
                else:
                    self._available = False
                    self._unavailable_reason = f"Ollama server reachable but returned status {r.status_code} at {self.base_url}."
            except Exception as e:
                self._available = False
                self._unavailable_reason = f"Failed connecting to Ollama at {self.base_url}: {e}"
            return self._available
        if self.provider == "openrouter":
            if not self._openrouter_api_key:
                self._available = False
                self._unavailable_reason = "Missing OPENROUTER_API_KEY."
                return self._available
            # Verify openai SDK importable OR be ready to fallback
            try:
                from openai import OpenAI as _OpenAIClass  # type: ignore  # noqa: F401
                if getattr(_OpenAIClass, "_is_stub", False):
                    self._available = True
                else:
                    self._available = True
            except Exception as e:
                self._available = True
                self._unavailable_reason = f"openai SDK import failed; will use direct HTTP fallback: {e}"
            return True
        self._available = False
        self._unavailable_reason = f"Unknown provider '{self.provider}'."
        return False

    def debug_status(self) -> Dict[str, Any]:
        """Return a dictionary summarizing adapter configuration & availability."""
        avail = self.available()
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "available": avail,
            "reason": None if avail else self._unavailable_reason,
        }

    def generate_plain(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.available():
            return None
        if self.provider == "ollama":
            res = self._ollama_chat(system_prompt=system_prompt, user_prompt=user_prompt, structured=False)
        elif self.provider == "openrouter":
            res = self._openrouter_chat(system_prompt=system_prompt, user_prompt=user_prompt, structured=False)
        else:
            return None
            
        if not res:
            return None
            
        # If the model ignored our 'plain-text' request and returned JSON anyway, 
        # try to extract the 'description' field.
        if isinstance(res, str) and (res.strip().startswith("{") or "```json" in res.lower()):
            obj = _JSONTools.try_parse_json(res)
            if isinstance(obj, dict):
                desc = obj.get("description") or obj.get("action") or obj.get("text")
                if desc:
                    return _JSONTools.sanitize_text(str(desc))
        
        return str(res)

    def generate_structured(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        if not self.available():
            logger.warning("DEBUG: generate_structured called but LLM is not available.")
            return None
            
        logger.info(f"DEBUG: generate_structured using provider: {self.provider}")
        if self.provider == "ollama":
            res = self._ollama_chat(system_prompt=system_prompt, user_prompt=user_prompt, structured=True)
        elif self.provider == "openrouter":
            res = self._openrouter_chat(system_prompt=system_prompt, user_prompt=user_prompt, structured=True)
        else:
            logger.error(f"DEBUG: generate_structured encountered unknown provider: {self.provider}")
            return None
        
        if res is None:
            logger.warning(f"DEBUG: generate_structured received None from provider {self.provider}")
        elif not isinstance(res, dict):
            logger.warning(f"DEBUG: generate_structured received non-dict from provider {self.provider}: {type(res)}")
            
        return res

    # Provider-specific implementation: Ollama (local)
    def _ollama_chat(self, system_prompt: str, user_prompt: str, structured: bool) -> Optional[Any]:
        import requests  # type: ignore
        url = self.base_url + "/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "num_ctx": 4096,
            },
        }
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code != 200:
                return None
            content = None
            try:
                data = r.json()
            except Exception:
                data = None

            if isinstance(data, dict):
                msg = data.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content") or msg.get("text")
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
                if content is None and isinstance(data.get("output"), list):
                    parts = []
                    for el in data.get("output"):
                        if isinstance(el, dict):
                            parts.append(el.get("content") or el.get("text") or "")
                        elif isinstance(el, str):
                            parts.append(el)
                    content = "\n".join(p for p in parts if p)
                if content is None:
                    if isinstance(data.get("result"), str):
                        content = data.get("result")
                    elif isinstance(data.get("result"), dict):
                        content = data.get("result").get("content") or data.get("result").get("text")
                if content is None:
                    content = data.get("content") or data.get("text")
            if not content:
                raw = r.text or ""
                content = raw.strip()

            if structured:
                obj = _JSONTools.try_parse_json(content)
                return obj
            return _JSONTools.sanitize_text(content or "")
        except Exception:
            return None

    # Provider-specific implementation: OpenRouter (remote API)
    def _openrouter_chat(self, system_prompt: str, user_prompt: str, structured: bool) -> Optional[Any]:
        sdk_client = None
        sdk_is_stub = False
        try:
            from openai import OpenAI  # type: ignore
            if getattr(OpenAI, "_is_stub", False):
                sdk_is_stub = True
            else:
                sdk_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self._openrouter_api_key)
        except Exception:
            sdk_client = None

        if not self._openrouter_api_key:
            return None

        headers = {}
        if self._openrouter_site:
            headers["HTTP-Referer"] = self._openrouter_site
        if self._openrouter_site_title:
            headers["X-Title"] = self._openrouter_site_title

        # Prepare models to try
        models_to_try = [self.model]
        if self._free_models_cache:
            # Add fallbacks that aren't the primary model
            models_to_try.extend([m for m in self._free_models_cache if m != self.model][:3])
        
        # Ensure stable fallbacks are in the list
        stable_fallbacks = [
            "meta-llama/llama-3.3-70b-instruct:free", 
            "meta-llama/llama-3.2-3b-instruct:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "google/gemini-flash-1.5:free"
        ]
        for fallback in stable_fallbacks:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        for model_id in models_to_try:
            if model_id in self._failed_models:
                continue
            
            # Use single-shot chat helper
            res = self._openrouter_chat_single(model_id, system_prompt, user_prompt, structured)
            if res is not None:
                if model_id != self.model:
                    logger.info(f"DEBUG: Successfully used fallback model: {model_id}")
                return res
            
            # If we failed, mark it
            logger.warning(f"DEBUG: Model {model_id} failed, marking as unusable for this session.")
            self._failed_models.add(model_id)
        
        return None

    def _openrouter_chat_single(self, model_id: str, system_prompt: str, user_prompt: str, structured: bool) -> Optional[Any]:
        """Attempt a single chat completion with exactly one model, no fallbacks."""
        sdk_client = None
        sdk_is_stub = False
        try:
            from openai import OpenAI  # type: ignore
            if getattr(OpenAI, "_is_stub", False):
                sdk_is_stub = True
            else:
                sdk_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self._openrouter_api_key)
        except Exception:
            sdk_client = None

        headers = {}
        if self._openrouter_site:
            headers["HTTP-Referer"] = self._openrouter_site
        if self._openrouter_site_title:
            headers["X-Title"] = self._openrouter_site_title
            
        # Try SDK first if available
        if sdk_client and not sdk_is_stub:
            try:
                completion = sdk_client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    extra_headers=headers or None,
                    temperature=0.2,
                    top_p=0.9,
                    max_tokens=1024 if structured else 256,
                )
                
                msg = completion.choices[0].message
                content = getattr(msg, "content", None)
                if not content and isinstance(msg, dict):
                    content = msg.get("content")
                
                if content:
                    logger.info(f"DEBUG: SDK request for {model_id} SUCCEEDED. Content length: {len(str(content))}")
                    if structured:
                        return _JSONTools.try_parse_json(str(content))
                    return _JSONTools.sanitize_text(str(content))
                else:
                    logger.warning(f"DEBUG: SDK request for {model_id} returned NO CONTENT.")
            except Exception as e:
                logger.warning(f"DEBUG: SDK request failed for {model_id}: {str(e)[:200]}")
                # Fall through to requests path for this model
        
        # Try direct requests path
        try:
            import requests
            http_headers = {
                "Authorization": f"Bearer {self._openrouter_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if self._openrouter_site:
                http_headers["HTTP-Referer"] = self._openrouter_site
            if self._openrouter_site_title:
                http_headers["X-Title"] = self._openrouter_site_title

            payload = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "top_p": 0.9,
                "max_tokens": 1024 if structured else 256,
            }
            
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions", 
                json=payload, 
                headers=http_headers, 
                timeout=20
            )
            
            if resp.status_code == 200:
                data = resp.json()
                logger.debug(f"DEBUG: HTTP 200 Response Data from {model_id}: {data}")
                content = None
                if isinstance(data, dict):
                    # Check for errors in the 200 response (some providers do this)
                    if "error" in data:
                        logger.warning(f"DEBUG: OpenRouter returned error in 200 payload for {model_id}: {data['error']}")
                        return None

                    choices = data.get("choices")
                    if isinstance(choices, list) and choices:
                        first = choices[0]
                        if isinstance(first, dict):
                            msg = first.get("message")
                            if isinstance(msg, dict):
                                content = msg.get("content")
                            if not content:
                                content = first.get("text") or first.get("content")
                
                if content:
                    logger.info(f"DEBUG: HTTP request for {model_id} SUCCEEDED. Content length: {len(str(content))}")
                    if structured:
                        return _JSONTools.try_parse_json(str(content))
                    return _JSONTools.sanitize_text(str(content))
                else:
                    logger.warning(f"DEBUG: HTTP request for {model_id} returned NO CONTENT in choices.")
            
            logger.warning(f"DEBUG: HTTP request failed for {model_id} with {resp.status_code}: {resp.text[:500]}")
        except Exception as e:
            logger.error(f"DEBUG: HTTP request exception for {model_id}: {e}", exc_info=True)
        
        return None


class MynxLLMAdapter(GenericLLMClient):
    """Legacy adapter for Mynx, now inheriting from GenericLLMClient."""

    def __init__(self):
        super().__init__()
        self._advisor = self._load_mynx_advisor()
        self._allowed_actions = set(self._advisor.get("behavior_profile", {}).get("typical_actions", []))
        self._system_prompt = self._advisor.get("system_prompt_snippet", "")
        self._example_struct = self._advisor.get("example_structured_response", {})

    def generate_plain(self, context: str) -> Optional[str]:
        user_prompt = self._build_user_prompt(context=context, structured=False)
        return super().generate_plain(system_prompt=self._system_prompt, user_prompt=user_prompt)

    def generate_structured(self, context: str) -> Optional[Dict[str, Any]]:
        user_prompt = self._build_user_prompt(context=context, structured=True)
        obj = super().generate_structured(system_prompt=self._system_prompt, user_prompt=user_prompt)
        if isinstance(obj, dict):
            valid = self._validate_structured(obj)
            if valid:
                return obj
            repaired = self._repair_structured(obj)
            if repaired and self._validate_structured(repaired):
                return repaired
        return None

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
                "CRITICAL: RETURN ONLY PLAIN TEXT, NO JSON, NO CODE FENCES. "
                f"Context: {ctx}"
            )

    def _validate_structured(self, obj: Dict[str, Any]) -> bool:
        required = {"action", "intensity", "description", "duration_seconds", "audible"}
        if not required.issubset(obj.keys()):
            return False
        if not isinstance(obj.get("action"), str):
            return False
        if obj["action"] not in self._allowed_actions:
            return False
        if not isinstance(obj.get("description"), str):
            return False
        obj["description"] = _JSONTools.sanitize_text(obj["description"])  # type: ignore
        return True

    def _repair_structured(self, obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        action = obj.get("action")
        desc = obj.get("description") or obj.get("text") or ""
        if not isinstance(desc, str):
            desc = str(desc)
        desc = _JSONTools.sanitize_text(desc)
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
            return {
                "behavior_profile": {"typical_actions": ["investigate_object", "groom", "play"]},
                "system_prompt_snippet": (
                    "You are an assistant for an in-game creature called the mynx. "
                    "Only produce nonverbal action descriptions or compact JSON action objects."
                ),
            }
