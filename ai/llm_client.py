import json
import os
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
try:
    import requests
except ImportError:
    requests = None
from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv()

AI_DIR = os.path.dirname(__file__)
MYNX_JSON_PATH = os.path.join(AI_DIR, "npc", "animal", "mynx.json")

# Disk cache for the ranked free-model list (survives process restarts)
_MODEL_CACHE_FILE = os.path.join(AI_DIR, ".model_cache.json")
_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours

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
      - model: 'llama3.1:7b' for ollama, first free OpenRouter model for openrouter (if unset)
    """

    # Ordered list of stable free OpenRouter models to use as fallbacks when
    # the dynamic cache is empty or all discovered models fail.
    # Gemini is listed first as it tends to be the most reliable.
    STABLE_FREE_FALLBACKS: List[str] = [
        "google/gemini-flash-1.5:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
    ]

    # --- Class-level shared state (process-wide) ---
    _free_models_cache: List[str] = []
    # Maps model_id -> datetime at which the failure penalty expires.
    _failed_models: Dict[str, datetime] = {}
    _discovery_done: bool = False
    # Lock protecting all mutations of _failed_models (called from multiple threads).
    _state_lock = threading.Lock()
    # In-flight guard: only one discovery fetch runs at a time.
    # All other threads wait on this event rather than launching duplicate fetches.
    _discovery_event: threading.Event = threading.Event()
    _discovery_event.set()  # Initially "done" so the first caller proceeds immediately.

    # -----------------------------------------------

    def __init__(self):
        self.enabled = os.getenv("MYNX_LLM_ENABLED", "0") in ("1", "true", "True")
        self.provider = os.getenv("MYNX_LLM_PROVIDER", "").strip().lower() or "ollama"
        self.model = os.getenv("MYNX_LLM_MODEL", "").strip() or "auto"
        logger.info(f"Initializing GenericLLMClient (Provider: {self.provider}, Model: {self.model}, Enabled: {self.enabled})")
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()

        # OpenRouter specific configuration
        self._openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self._openrouter_site = os.getenv("OPENROUTER_SITE", "").strip() or None
        self._openrouter_site_title = os.getenv("OPENROUTER_SITE_TITLE", "").strip() or None

        # Probe availability lazily; we don't want to fail import-time
        self._available: Optional[bool] = None
        self._unavailable_reason: Optional[str] = None

        # Discover models (singleton: discovery only runs once per process)
        if self.enabled:
            if self.provider == "ollama" and not os.getenv("MYNX_LLM_MODEL"):
                self._discover_ollama_model()
            elif self.provider == "openrouter":
                if not GenericLLMClient._discovery_done:
                    self._discover_openrouter_model()
                self._validate_and_fallback_openrouter()

    @classmethod
    def reset_class_state(cls) -> None:
        """Reset all class-level shared state. Intended for use in tests only."""
        with cls._state_lock:
            cls._free_models_cache = []
            cls._failed_models = {}
            cls._discovery_done = False
        # Ensure the event is set so tests don't deadlock waiting on a discovery
        cls._discovery_event.set()

    # ------------------------------------------------------------------
    # Model discovery
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Disk cache helpers (Chester-style)
    # ------------------------------------------------------------------

    @staticmethod
    def _read_disk_cache() -> Optional[List[str]]:
        """Read and validate the on-disk model cache. Returns model list or None."""
        try:
            with open(_MODEL_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            fetched_at = data.get("fetched_at", 0)
            models = data.get("models", [])
            if not isinstance(models, list) or not models:
                return None
            if not all(isinstance(m, str) and m for m in models):
                return None
            age_seconds = (datetime.now().timestamp() - fetched_at)
            if age_seconds > _CACHE_TTL_SECONDS:
                return None
            return models
        except Exception:
            return None

    @staticmethod
    def _write_disk_cache(models: List[str]) -> None:
        """Atomically write the ranked model list to disk."""
        payload = json.dumps({"fetched_at": datetime.now().timestamp(), "models": models}, indent=2)
        tmp = _MODEL_CACHE_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp, _MODEL_CACHE_FILE)  # atomic on POSIX and Windows
        except Exception as e:
            logger.warning(f"Failed to write model cache: {e}")

    # ------------------------------------------------------------------
    # Model ranking (Chester-style)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_free_text_model(m: dict) -> bool:
        """Return True if the model has zero-cost prompt+completion AND text-only output."""
        pricing = m.get("pricing", {})
        try:
            if float(pricing.get("prompt", 1)) != 0:
                return False
            if float(pricing.get("completion", 1)) != 0:
                return False
        except (ValueError, TypeError):
            return False
        output_mods = m.get("architecture", {}).get("output_modalities", [])
        if output_mods and not all(mod == "text" for mod in output_mods):
            return False
        return True

    @classmethod
    def _rank_models(cls, all_models: List[dict], priority_ids: set) -> List[str]:
        """Filter to free text-only models, deduplicate, rank, and return IDs.

        Ranking axes (same priority order as Chester's modelManager.js):
          1. Priority category (roleplay/gaming) tagged first
          2. Recency (newer created timestamp = more maintained)
          3. Context window size (smallest = fastest / lightest)
          4. Stable alphabetical tiebreaker
        """
        seen: set = set()
        eligible = []
        for m in all_models:
            mid = m.get("id")
            if not mid or mid in seen:
                continue
            if not cls._is_free_text_model(m):
                continue
            seen.add(mid)
            eligible.append(m)

        eligible.sort(key=lambda m: (
            0 if m["id"] in priority_ids else 1,   # 1. priority category first
            -(m.get("created") or 0),               # 2. newest first (negate for DESC)
            m.get("context_length") or float("inf"),# 3. smallest context first
            m["id"],                                # 4. stable tiebreaker
        ))
        return [m["id"] for m in eligible]

    @classmethod
    def _fetch_and_rank_models(cls, api_key: str) -> List[str]:
        """Fetch all free OpenRouter models, merge with gaming category, rank, cache."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": os.getenv("OPENROUTER_SITE", ""),
            "X-Title": os.getenv("OPENROUTER_SITE_TITLE", ""),
        }

        def fetch(url):
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json().get("data", [])

        # Fetch the gaming/roleplay category and all models in parallel via threads
        priority_raw: List[dict] = []
        all_raw: List[dict] = []
        errors: List[str] = []

        def fetch_priority():
            try:
                # Try 'gaming' first; fall back to 'roleplay'
                for cat in ("gaming", "roleplay"):
                    data = fetch(f"https://openrouter.ai/api/v1/models?category={cat}")
                    if data:
                        priority_raw.extend(data)
                        return
            except Exception as e:
                errors.append(str(e))

        def fetch_all():
            try:
                all_raw.extend(fetch("https://openrouter.ai/api/v1/models"))
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=fetch_priority, daemon=True)
        t2 = threading.Thread(target=fetch_all, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=12); t2.join(timeout=12)

        if not all_raw:
            raise RuntimeError(f"Failed to fetch OpenRouter models: {'; '.join(errors)}")

        priority_ids = {m.get("id") for m in priority_raw if m.get("id")}
        # Priority models lead the merged list so deduplication in _rank_models
        # always retains the priority copy when IDs overlap.
        merged = priority_raw + all_raw
        ranked = cls._rank_models(merged, priority_ids)

        if not ranked:
            raise RuntimeError("No suitable free text-only models found on OpenRouter.")

        cls._write_disk_cache(ranked)
        logger.info(f"Discovered and ranked {len(ranked)} free OpenRouter models.")
        return ranked

    # ------------------------------------------------------------------
    # Model discovery — with in-flight lock to prevent concurrent storms
    # ------------------------------------------------------------------

    def _discover_openrouter_model(self):
        """Populate the class-level free-model cache (disk → memory → network).

        Uses a threading.Event to coalesce concurrent callers: the first caller
        does the work; all others wait for it to finish instead of launching
        duplicate network requests.
        """
        if not self._openrouter_api_key:
            GenericLLMClient._discovery_done = True
            return

        # If a discovery is already in-flight, wait for it then return.
        if not GenericLLMClient._discovery_event.is_set():
            logger.info("Discovery already in-flight, waiting...")
            GenericLLMClient._discovery_event.wait(timeout=20)
            return

        # We're the first caller — take the lock.
        GenericLLMClient._discovery_event.clear()
        try:
            # 1. Try the in-memory list (already populated by a previous instance)
            if GenericLLMClient._free_models_cache:
                self._select_model_from_cache(GenericLLMClient._free_models_cache)
                return

            # 2. Try the disk cache
            cached = self._read_disk_cache()
            if cached:
                logger.info(f"Loaded {len(cached)} models from disk cache.")
                GenericLLMClient._free_models_cache = cached
                self._select_model_from_cache(cached)
                GenericLLMClient._discovery_done = True
                return

            # 3. Fetch from network
            ranked = self._fetch_and_rank_models(self._openrouter_api_key)
            GenericLLMClient._free_models_cache = ranked
            self._select_model_from_cache(ranked)
            GenericLLMClient._discovery_done = True

            # Kick off a nightly refresh background thread (idempotent)
            self._start_nightly_refresh()

        except Exception as e:
            logger.warning(f"Failed to discover OpenRouter models: {e}")
            # Mark done so we don't retry on every instantiation; rely on STABLE_FREE_FALLBACKS
            GenericLLMClient._discovery_done = True
        finally:
            # Always release the event so waiting threads unblock
            GenericLLMClient._discovery_event.set()

    def _select_model_from_cache(self, models: List[str]) -> None:
        """Pick a primary model from the ranked list when model is set to auto."""
        if self.model not in ("auto", "free", "") and self.model:
            return  # User explicitly specified a model; respect it
        self.model = models[0] if models else self.STABLE_FREE_FALLBACKS[0]

    @classmethod
    def _start_nightly_refresh(cls) -> None:
        """Schedule a background thread that refreshes the model cache every 24 hours."""
        if getattr(cls, "_nightly_refresh_started", False):
            return
        cls._nightly_refresh_started = True

        def _refresh_loop():
            import time
            while True:
                time.sleep(_CACHE_TTL_SECONDS)
                try:
                    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
                    if not api_key:
                        continue
                    ranked = cls._fetch_and_rank_models(api_key)
                    with cls._state_lock:
                        cls._free_models_cache = ranked
                    logger.info("Nightly model refresh complete.")
                except Exception as e:
                    logger.warning(f"Nightly model refresh failed: {e}")

        t = threading.Thread(target=_refresh_loop, daemon=True, name="llm-model-refresh")
        t.start()
        logger.info("Nightly model refresh thread started.")


    # ------------------------------------------------------------------
    # Validation / fallback selection
    # ------------------------------------------------------------------

    def _validate_and_fallback_openrouter(self):
        """Test the current model and fallback through others until one works."""
        if not self.enabled or not self._openrouter_api_key:
            return

        logger.info(f"Validating OpenRouter model: {self.model}")

        # Tiny test chat to verify connectivity and availability (short timeout)
        def test_one(m_id: str) -> bool:
            if self._is_model_failed(m_id):
                return False
            try:
                res = self._openrouter_chat_single(m_id, "System", "Say OK", False, timeout=5)
                return res is not None and "ok" in str(res).lower()
            except Exception:
                return False

        if test_one(self.model):
            logger.info(f"Primary model {self.model} verified.")
            self._available = True
            return

        logger.warning(f"Primary model {self.model} failed. Searching for fallback...")
        self._mark_model_failed(self.model, duration_minutes=30)

        # Build candidate list: dynamic free cache first, then static stable list
        candidates: List[str] = []
        if GenericLLMClient._free_models_cache:
            candidates.extend([m for m in GenericLLMClient._free_models_cache if m != self.model])
        for s in self.STABLE_FREE_FALLBACKS:
            if s not in candidates and s != self.model:
                candidates.append(s)

        for cand in candidates[:5]:  # Try at most 5 fallbacks during validation
            if self._is_model_failed(cand):
                continue
            logger.info(f"Testing fallback: {cand}")
            if test_one(cand):
                logger.info(f"Found working fallback: {cand}")
                self.model = cand
                self._available = True
                return
            else:
                self._mark_model_failed(cand, duration_minutes=15)

        logger.error("All OpenRouter models failed validation. Disabling LLM.")
        self._available = False
        self.enabled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def available(self) -> bool:
        if not self.enabled:
            self._unavailable_reason = "Adapter disabled (set MYNX_LLM_ENABLED=1 to enable)."
            return False
        if self._available is not None:
            return self._available

        logger.info(f"Probing availability for {self.provider}")
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
                return False
            # Availability was already confirmed (or denied) during _validate_and_fallback_openrouter.
            # If we reach here it means the openrouter path was skipped (e.g. disabled at init time),
            # so we mark as available and let the actual request determine if things work.
            self._available = True
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
            logger.warning("generate_structured called but LLM is not available.")
            return None

        logger.info(f"generate_structured using provider: {self.provider}")
        if self.provider == "ollama":
            res = self._ollama_chat(system_prompt=system_prompt, user_prompt=user_prompt, structured=True)
        elif self.provider == "openrouter":
            res = self._openrouter_chat(system_prompt=system_prompt, user_prompt=user_prompt, structured=True)
        else:
            logger.error(f"generate_structured encountered unknown provider: {self.provider}")
            return None

        if res is None:
            logger.warning(f"generate_structured received None from provider {self.provider}")
        elif not isinstance(res, dict):
            logger.warning(f"generate_structured received non-dict from provider {self.provider}: {type(res)}")

        return res

    # ------------------------------------------------------------------
    # Provider: Ollama (local)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Provider: OpenRouter (remote API)
    # ------------------------------------------------------------------

    def _get_sdk_client(self) -> Optional[Any]:
        """Return an OpenAI SDK client configured for OpenRouter, or None if unavailable/stubbed."""
        try:
            from openai import OpenAI  # type: ignore
            if getattr(OpenAI, "_is_stub", False):
                return None
            return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self._openrouter_api_key)
        except Exception:
            return None

    def _build_openrouter_headers(self) -> Dict[str, str]:
        """Build extra HTTP headers for OpenRouter ranking metadata."""
        headers: Dict[str, str] = {}
        if self._openrouter_site:
            headers["HTTP-Referer"] = self._openrouter_site
        if self._openrouter_site_title:
            headers["X-Title"] = self._openrouter_site_title
        return headers

    def _openrouter_chat(self, system_prompt: str, user_prompt: str, structured: bool) -> Optional[Any]:
        if not self._openrouter_api_key:
            return None

        # Build the ordered list of models to try
        models_to_try: List[str] = [self.model]
        if GenericLLMClient._free_models_cache:
            models_to_try.extend(
                [m for m in GenericLLMClient._free_models_cache if m != self.model][:5]
            )
        for fallback in self.STABLE_FREE_FALLBACKS:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        attempts = 0
        max_attempts = 3  # Primary + up to 2 fallbacks per request

        for model_id in models_to_try:
            if self._is_model_failed(model_id):
                continue

            attempts += 1
            if attempts > max_attempts:
                logger.warning(f"Reached max attempts ({max_attempts}) for LLM request. Stopping.")
                break

            # Use a shorter timeout for fallback attempts to fail fast
            timeout = 20 if attempts == 1 else 10
            res = self._openrouter_chat_single(model_id, system_prompt, user_prompt, structured, timeout=timeout)
            if res is not None:
                if model_id != self.model:
                    logger.info(f"Successfully used fallback model: {model_id}")
                return res

            logger.warning(f"Model {model_id} failed, marking as unusable.")
            self._mark_model_failed(model_id)

        return None

    def _openrouter_chat_single(
        self,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        structured: bool,
        timeout: int = 20,
    ) -> Optional[Any]:
        """Attempt a single chat completion with exactly one model, no fallbacks."""
        sdk_client = self._get_sdk_client()
        extra_headers = self._build_openrouter_headers()

        # Try SDK first if available
        if sdk_client is not None:
            try:
                completion = sdk_client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    extra_headers=extra_headers or None,
                    temperature=0.2,
                    top_p=0.9,
                    max_tokens=1024 if structured else 256,
                )

                content = getattr(completion.choices[0].message, "content", None)

                if content:
                    logger.info(f"SDK request for {model_id} SUCCEEDED. Content length: {len(str(content))}")
                    if structured:
                        return _JSONTools.try_parse_json(str(content))
                    return _JSONTools.sanitize_text(str(content))
                else:
                    logger.warning(f"SDK request for {model_id} returned no content.")
            except Exception as e:
                logger.warning(f"SDK request failed for {model_id}: {str(e)[:200]}")
                # Fall through to the direct HTTP path

        # Direct HTTP fallback
        try:
            import requests
            http_headers = {
                "Authorization": f"Bearer {self._openrouter_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                **extra_headers,
            }

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
                timeout=timeout,
            )

            if resp.status_code == 429:
                logger.warning(f"OpenRouter returned 429 Rate Limit for {model_id}")
                # Short penalty — don't let the caller overwrite with a longer one
                self._mark_model_failed(model_id, duration_minutes=2)
                return None

            if resp.status_code == 200:
                data = resp.json()
                logger.debug(f"HTTP 200 response from {model_id}: {data}")
                content = None
                if isinstance(data, dict):
                    # Some providers embed errors inside a 200 payload
                    if "error" in data:
                        logger.warning(f"OpenRouter returned error in 200 payload for {model_id}: {data['error']}")
                        return None

                    choices = data.get("choices")
                    if isinstance(choices, list) and choices:
                        first = choices[0]
                        if isinstance(first, dict):
                            msg = first.get("message")
                            if isinstance(msg, dict):
                                # Fall back to 'reasoning' for thinking-mode models
                                content = msg.get("content") or msg.get("reasoning")
                            if not content:
                                content = first.get("text") or first.get("content") or first.get("reasoning")

                if content:
                    logger.info(f"HTTP request for {model_id} SUCCEEDED. Content length: {len(str(content))}")
                    if structured:
                        return _JSONTools.try_parse_json(str(content))
                    return _JSONTools.sanitize_text(str(content))
                else:
                    logger.warning(f"HTTP request for {model_id} returned no content in choices.")

            logger.warning(f"HTTP request failed for {model_id} with {resp.status_code}: {resp.text[:500]}")
        except Exception as e:
            logger.error(f"HTTP request exception for {model_id}: {e}", exc_info=True)

        return None

    # ------------------------------------------------------------------
    # Model failure tracking (thread-safe)
    # ------------------------------------------------------------------

    def _is_model_failed(self, model_id: str) -> bool:
        """Return True if model_id is currently within its failure penalty window."""
        with GenericLLMClient._state_lock:
            expiry = GenericLLMClient._failed_models.get(model_id)
            if expiry is None:
                return False
            if datetime.now() > expiry:
                del GenericLLMClient._failed_models[model_id]
                return False
            return True

    def _mark_model_failed(self, model_id: str, duration_minutes: int = 10) -> None:
        """Mark a model as failed for a specified duration.

        If the model is already penalized, the penalty is only extended — never
        shortened. This prevents a generic 10-minute caller penalty from clobbering
        a deliberate 2-minute 429 penalty set by the inner request method.
        """
        with GenericLLMClient._state_lock:
            new_expiry = datetime.now() + timedelta(minutes=duration_minutes)
            existing = GenericLLMClient._failed_models.get(model_id)
            if existing is None or new_expiry > existing:
                GenericLLMClient._failed_models[model_id] = new_expiry
                logger.info(f"Model {model_id} marked as failed until {new_expiry.strftime('%H:%M:%S')}")


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


# ---------------------------------------------------------------------------
# NPC Chat adapter — conversational human NPCs
# ---------------------------------------------------------------------------

_NPC_CHAT_HUMAN_DIR = os.path.join(AI_DIR, "npc", "human")
_NPC_CHAT_WORLD_FACTS_PATH = os.path.join(_NPC_CHAT_HUMAN_DIR, "world_facts.json")


class NpcChatLLMAdapter(GenericLLMClient):
    """LLM adapter for conversational human NPC dialogue.

    Provides three generation methods used by HumanNPCLLMMixin:
      - generate_personality: one-shot personality seeding for generic nomads
      - generate_npc_turn:    NPC opening line or response; returns structured JSON
      - generate_jean_options: three Jean dialogue options in a single call

    Configuration (re-uses the Mynx env vars plus one new gate):
      NPC_CHAT_LLM_ENABLED=1      gate specifically for human NPC chat
      NPC_CHAT_TEMP_PERSONALITY   float override for personality call (default 0.7)
      NPC_CHAT_TEMP_NPC           float override for NPC turn call (default 0.65)
      NPC_CHAT_TEMP_OPTIONS       float override for Jean options call (default 0.8)
    """

    # Per-class singleton cache so we don't re-init the adapter on every API call.
    _instances: Dict[str, "NpcChatLLMAdapter"] = {}
    _instances_lock = threading.Lock()

    def __init__(self):
        super().__init__()
        # Override the enabled check: use NPC_CHAT_LLM_ENABLED
        self.enabled = os.getenv("NPC_CHAT_LLM_ENABLED", "0") in ("1", "true", "True")
        self._world_facts: Optional[Dict[str, Any]] = None
        self._load_world_facts()

    @classmethod
    def get_instance(cls) -> "NpcChatLLMAdapter":
        """Return the shared adapter instance, creating it on first call."""
        with cls._instances_lock:
            if "default" not in cls._instances:
                cls._instances["default"] = cls()
            return cls._instances["default"]

    def _load_world_facts(self) -> None:
        try:
            with open(_NPC_CHAT_WORLD_FACTS_PATH, "r", encoding="utf-8") as f:
                self._world_facts = json.load(f)
        except Exception:
            self._world_facts = {
                "world_name": "Aurelion",
                "allowed_proper_nouns": ["Jean", "Gorran", "Mara", "Devet", "Liss",
                                         "Aurelion", "Grondia", "Badlands", "Echoing Caves"],
                "tone_notes": "Low fantasy, grounded, practical.",
            }

    def _world_facts_block(self) -> str:
        if not self._world_facts:
            return "Setting: Aurelion, a low-fantasy world."
        wf = self._world_facts
        geo = ", ".join(wf.get("geography", []))
        factions = ", ".join(wf.get("factions_and_peoples", []))
        rules = " ".join(wf.get("world_rules", []))
        tone = wf.get("tone_notes", "")
        return (
            f"WORLD: {wf.get('world_name','Aurelion')}. {wf.get('brief_description','')}\n"
            f"Places: {geo}.\nPeoples: {factions}.\n{rules}\nTone: {tone}"
        )

    # ------------------------------------------------------------------
    # Call 1 — Personality generation (generic nomads, once per instance)
    # ------------------------------------------------------------------

    def generate_personality(self, npc_class_display: str) -> Optional[Dict[str, Any]]:
        """Generate a unique personality seed for a generic nomad NPC.

        Returns dict with keys: given_name, voice, knowledge, attitude_to_strangers,
        speech_sample, loquacity_base.
        Returns None if LLM unavailable.
        """
        if not self.enabled:
            return None

        system = (
            "You are a character generator for a low-fantasy text RPG set in Aurelion. "
            "Generate a distinct personality for a nomad NPC. "
            "Return ONLY valid JSON. No commentary, no code fences."
        )
        wf = self._world_facts or {}
        allowed = ", ".join(wf.get("allowed_proper_nouns", []))
        user = (
            f"Generate personality JSON for a {npc_class_display}. "
            "Return exactly these keys:\n"
            '"given_name": a simple nomadic first name (no invented proper nouns),\n'
            '"voice": one sentence describing speech rhythm (e.g. "sparse, declarative"),\n'
            '"knowledge": list of 2 topics this person knows well,\n'
            '"attitude_to_strangers": one of "wary", "indifferent", "curious", "guarded",\n'
            '"speech_sample": one in-character line (10-20 words),\n'
            '"loquacity_base": integer 40-90 representing social patience.\n'
            f"Do NOT invent locations, factions, or creatures not in: {allowed}."
        )
        temp = float(os.getenv("NPC_CHAT_TEMP_PERSONALITY", "0.7"))
        raw = self._call_llm(system, user, max_tokens=256, temperature=temp)
        if not raw:
            return None
        parsed = _JSONTools.try_parse_json(raw)
        if not isinstance(parsed, dict):
            return None
        required = {"given_name", "voice", "knowledge", "attitude_to_strangers",
                    "speech_sample", "loquacity_base"}
        if not required.issubset(parsed.keys()):
            return None
        return parsed

    # ------------------------------------------------------------------
    # Call 2 — NPC turn (opening line + each NPC response)
    # ------------------------------------------------------------------

    def generate_npc_turn(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        is_opening: bool,
        jean_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate one NPC conversational turn.

        Returns dict: {npc_text, conversation_quality, conversation_end}
        conversation_quality: "positive" | "neutral" | "negative" | "offensive"
        conversation_end: bool
        """
        if not self.enabled:
            return None

        history_block = self._format_history(history)
        if is_opening:
            task = "Generate the NPC's opening line. Vary it — do not repeat anything in the history above. Do not begin with 'Hello' or 'Greetings'."
        else:
            task = f'Jean said: "{jean_text}". Generate the NPC\'s response.'

        user = (
            f"{history_block}\n\n"
            f"[TASK]\n{task}\n\n"
            "Return ONLY this JSON (no code fences, no extra keys):\n"
            '{"npc_text": "...", "conversation_quality": "positive|neutral|negative|offensive", "conversation_end": false}\n'
            "conversation_quality reflects how the NPC felt about this exchange: "
            "positive=enjoyed/interested, neutral=tolerated, negative=annoyed/offended, offensive=deeply offended.\n"
            "Set conversation_end to true ONLY if the NPC is done talking entirely (loquacity exhausted or deeply offended)."
        )

        temp = float(os.getenv("NPC_CHAT_TEMP_NPC", "0.65"))
        raw = self._call_llm(system_prompt, user, max_tokens=300, temperature=temp)
        if not raw:
            return None
        parsed = _JSONTools.try_parse_json(raw)
        if not isinstance(parsed, dict):
            return None
        if "npc_text" not in parsed or not isinstance(parsed["npc_text"], str):
            return None
        # Normalise fields
        valid_qualities = {"positive", "neutral", "negative", "offensive"}
        quality = str(parsed.get("conversation_quality", "neutral")).lower()
        if quality not in valid_qualities:
            quality = "neutral"
        parsed["conversation_quality"] = quality
        parsed["conversation_end"] = bool(parsed.get("conversation_end", False))
        parsed["npc_text"] = _JSONTools.sanitize_text(parsed["npc_text"])
        return parsed

    # ------------------------------------------------------------------
    # Call 3 — Jean's three response options (single call)
    # ------------------------------------------------------------------

    def generate_jean_options(
        self,
        npc_name: str,
        npc_voice_summary: str,
        last_npc_line: str,
        history: List[Dict[str, str]],
        turn: int,
    ) -> Optional[List[Dict[str, str]]]:
        """Generate three Jean dialogue options with varied tones.

        Returns list of 3 dicts: [{tone, text}, ...]
        tones: "direct", "guarded", "open"
        """
        if not self.enabled:
            return None

        system = (
            "You generate player dialogue options for a text RPG. "
            "The player is Jean (he/him), a cautious, observant traveler in a low-fantasy world. "
            "Jean is not heroic in a loud way. He is measured, careful, occasionally guarded. "
            "Generate options that are plausible for Jean. Never have Jean reveal information he would not know. "
            "Keep each option 8-20 words. Return ONLY valid JSON. No commentary, no code fences."
        )

        recent_jean_lines = [ex.get("jean", "") for ex in history[-4:] if ex.get("jean")]
        history_hint = " | ".join(recent_jean_lines) if recent_jean_lines else "none yet"

        user = (
            f"NPC: {npc_name} — {npc_voice_summary}\n"
            f'{npc_name} just said: "{last_npc_line}"\n\n'
            f"Jean's recent lines (avoid repeating these): {history_hint}\n\n"
            "Generate exactly 3 Jean response options. Return this JSON array:\n"
            '[{"tone": "direct", "text": "..."}, {"tone": "guarded", "text": "..."}, {"tone": "open", "text": "..."}]\n\n'
            "Rules:\n"
            "- direct: brief, factual, Jean gets to the point\n"
            "- guarded: Jean deflects, doesn't commit, or keeps his distance\n"
            "- open: Jean engages with some warmth or genuine curiosity\n"
            "- No option may echo the recent history above\n"
            "- All options must be plausible for a careful, measured human traveler\n"
            f"- This is turn {turn} of the conversation — options should feel natural for mid-conversation, not just openers"
        )

        temp = float(os.getenv("NPC_CHAT_TEMP_OPTIONS", "0.8"))
        raw = self._call_llm(system, user, max_tokens=300, temperature=temp)
        if not raw:
            return None
        # Try parsing as list
        raw = raw.strip()
        if raw.startswith("```"):
            raw = "\n".join(l for l in raw.splitlines() if not l.strip().startswith("```")).strip()
        try:
            parsed = json.loads(raw)
        except Exception:
            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1:
                try:
                    parsed = json.loads(raw[start:end + 1])
                except Exception:
                    return None
            else:
                return None
        if not isinstance(parsed, list) or len(parsed) < 3:
            return None
        result = []
        expected_tones = ["direct", "guarded", "open"]
        for i, item in enumerate(parsed[:3]):
            if not isinstance(item, dict) or "text" not in item:
                return None
            tone = str(item.get("tone", expected_tones[i])).lower()
            if tone not in expected_tones:
                tone = expected_tones[i]
            result.append({"tone": tone, "text": str(item["text"])[:200]})
        return result

    # ------------------------------------------------------------------
    # Internal LLM call dispatcher
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Optional[str]:
        """Dispatch to the active provider. Returns raw text or None."""
        if not self.enabled:
            return None
        if self.provider == "ollama":
            return self._call_ollama(system_prompt, user_prompt, max_tokens, temperature)
        elif self.provider == "openrouter":
            return self._call_openrouter(system_prompt, user_prompt, max_tokens, temperature)
        return None

    def _call_ollama(
        self, system: str, user: str, max_tokens: int, temperature: float
    ) -> Optional[str]:
        if requests is None:
            return None
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "top_p": 0.9,
                },
            }
            r = requests.post(
                self.base_url + "/api/chat",
                json=payload,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content", "").strip() or None
        except Exception as e:
            logger.warning(f"NpcChatLLMAdapter Ollama error: {e}")
            return None

    def _call_openrouter(
        self, system: str, user: str, max_tokens: int, temperature: float
    ) -> Optional[str]:
        if requests is None or not self._openrouter_api_key:
            return None
        model = self._get_openrouter_model()
        if not model:
            return None
        headers = {
            "Authorization": f"Bearer {self._openrouter_api_key}",
            "Content-Type": "application/json",
        }
        if self._openrouter_site:
            headers["HTTP-Referer"] = self._openrouter_site
        if self._openrouter_site_title:
            headers["X-Title"] = self._openrouter_site_title
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
        }
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=45,
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip() or None
        except Exception as e:
            logger.warning(f"NpcChatLLMAdapter OpenRouter error: {e}")
            return None

    def _get_openrouter_model(self) -> Optional[str]:
        """Return the configured model or the first available free model."""
        if self.model and self.model != "auto":
            return self.model
        if GenericLLMClient._free_models_cache:
            return GenericLLMClient._free_models_cache[0]
        return self.STABLE_FREE_FALLBACKS[0]

    @staticmethod
    def _format_history(history: List[Dict[str, str]]) -> str:
        if not history:
            return "[CONVERSATION HISTORY]\nNone yet."
        lines = ["[CONVERSATION HISTORY]"]
        for ex in history[-8:]:
            npc_line = ex.get("npc", "")
            jean_line = ex.get("jean", "")
            if npc_line:
                lines.append(f"NPC: {npc_line}")
            if jean_line:
                lines.append(f"Jean: {jean_line}")
        return "\n".join(lines)
