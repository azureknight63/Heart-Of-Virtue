"""Discord digest for LLM provider usage.

Mirrors the shape of the Chester project's weekly analytics report: an embed
posted to an incoming webhook, skipped without complaint when no webhook is
configured, built from a snapshot-and-reset so each digest covers one window.

The subject matter is this project's own: which providers served traffic, how
much free-tier headroom is left, and how often a model had to be benched for
returning something unparseable.
"""

import ai.provider_digest as digest
from ai.llm_client import GenericLLMClient


class _Resp:
    def __init__(self, status=204):
        self.status_code = status
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %s" % self.status_code)


class _HeaderResp:
    def __init__(self, headers=None, status=200):
        self.headers = headers or {}
        self.status_code = status


def _record(provider, limit=None, remaining=None, outcome="ok"):
    headers = {}
    if limit is not None:
        headers = {
            "x-ratelimit-limit": str(limit),
            "x-ratelimit-remaining": str(remaining),
        }
    GenericLLMClient._record_provider_usage(provider, _HeaderResp(headers), outcome)


class TestSnapshotAndReset:
    def setup_method(self):
        GenericLLMClient.reset_class_state()

    def teardown_method(self):
        GenericLLMClient.reset_class_state()

    def test_counters_are_cleared_for_the_next_window(self):
        _record("groq", 100, 50)
        _record("groq", 100, 49)
        first = GenericLLMClient.snapshot_and_reset()
        assert first["providers"]["groq"]["requests"] == 2

        second = GenericLLMClient.snapshot_and_reset()
        assert second["providers"]["groq"]["requests"] == 0

    def test_current_headroom_survives_the_reset(self):
        """Saturation describes now, not the window — it must not be zeroed."""
        _record("groq", 100, 10)
        GenericLLMClient.snapshot_and_reset()
        after = GenericLLMClient.provider_saturation()
        assert after["providers"]["groq"]["saturation"] == 0.9

    def test_window_start_advances(self):
        first = GenericLLMClient.snapshot_and_reset()
        second = GenericLLMClient.snapshot_and_reset()
        assert second["window_start"] >= first["window_start"]


class TestBuildDigest:
    def setup_method(self):
        GenericLLMClient.reset_class_state()

    def teardown_method(self):
        GenericLLMClient.reset_class_state()

    def _snapshot(self):
        _record("openrouter", 50, 0, outcome="rate_limited")
        _record("groq", 6000, 5100)
        return GenericLLMClient.snapshot_and_reset()

    def test_embed_has_the_expected_skeleton(self):
        embed = digest.build_digest(self._snapshot())
        assert embed["title"]
        assert isinstance(embed["fields"], list) and embed["fields"]
        assert embed["footer"]["text"]
        assert embed["timestamp"]
        assert isinstance(embed["color"], int)

    def test_every_provider_appears(self):
        blob = str(digest.build_digest(self._snapshot()))
        assert "openrouter" in blob
        assert "groq" in blob

    def test_exhausted_provider_is_called_out(self):
        blob = str(digest.build_digest(self._snapshot()))
        assert "100%" in blob

    def test_worst_provider_is_listed_first_and_unknowns_last(self):
        _record("openrouter", 50, 0, outcome="rate_limited")
        _record("groq", 100, 90)
        _record("cerebras", outcome="error")
        text = digest.format_saturation(GenericLLMClient.snapshot_and_reset())
        lines = [ln for ln in text.splitlines() if ln.startswith("`")]
        assert lines[0].startswith("`openrouter`")
        assert lines[-1].startswith("`cerebras`")

    def test_empty_snapshot_still_builds(self):
        embed = digest.build_digest(GenericLLMClient.snapshot_and_reset())
        assert embed["fields"]

    def test_sections_are_configurable(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_SECTIONS", "saturation")
        names = [f["name"] for f in digest.build_digest(self._snapshot())["fields"]]
        assert any("Saturation" in n for n in names)
        assert not any("Reliability" in n for n in names)

    def test_unknown_section_names_are_ignored(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_SECTIONS", "saturation,nonsense")
        assert digest.build_digest(self._snapshot())["fields"]


class TestSendDigest:
    def setup_method(self):
        GenericLLMClient.reset_class_state()

    def teardown_method(self):
        GenericLLMClient.reset_class_state()

    def test_missing_webhook_is_a_quiet_skip(self, monkeypatch):
        posted = []
        monkeypatch.delenv("HOV_ANALYTICS_WEBHOOK_URL", raising=False)
        monkeypatch.setattr(digest.requests, "post", lambda *a, **k: posted.append(1))
        assert digest.send_digest() is False
        assert posted == []

    def test_posts_an_embed_to_the_webhook(self, monkeypatch):
        sent = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            sent["url"] = url
            sent["json"] = json
            return _Resp()

        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.test/hook")
        monkeypatch.setattr(digest.requests, "post", fake_post)
        _record("groq", 100, 50)

        assert digest.send_digest() is True
        assert sent["url"] == "https://discord.test/hook"
        assert "embeds" in sent["json"]
        assert len(sent["json"]["embeds"]) == 1

    def test_a_failed_post_does_not_raise(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("discord is down")

        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.test/hook")
        monkeypatch.setattr(digest.requests, "post", boom)
        assert digest.send_digest() is False

    def test_http_error_does_not_raise(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.test/hook")
        monkeypatch.setattr(digest.requests, "post", lambda *a, **k: _Resp(500))
        assert digest.send_digest() is False

    def test_a_failed_post_keeps_the_window_open(self, monkeypatch):
        """An outage costs a digest, not the traffic it was describing."""
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.test/hook")
        monkeypatch.setattr(digest.requests, "post", lambda *a, **k: _Resp(500))
        _record("groq", 100, 50)
        assert digest.send_digest() is False
        providers = GenericLLMClient.provider_saturation()["providers"]
        assert providers["groq"]["requests"] == 1

    def test_sending_resets_the_window(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.test/hook")
        monkeypatch.setattr(digest.requests, "post", lambda *a, **k: _Resp())
        _record("groq", 100, 50)
        digest.send_digest()
        assert GenericLLMClient.provider_saturation()["providers"]["groq"]["requests"] == 0


class TestDigestScheduler:
    """The digest is worthless if nothing ever fires it."""

    def setup_method(self):
        digest._scheduler_started = False

    def teardown_method(self):
        digest._scheduler_started = False

    def test_no_webhook_means_no_thread(self, monkeypatch):
        started = []
        monkeypatch.delenv("HOV_ANALYTICS_WEBHOOK_URL", raising=False)
        monkeypatch.setattr(digest.threading, "Thread", lambda **kw: started.append(kw))
        assert digest.start_digest_scheduler() is False
        assert started == []

    def test_zero_interval_disables_it(self, monkeypatch):
        started = []
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.test/h")
        monkeypatch.setenv("HOV_ANALYTICS_INTERVAL_HOURS", "0")
        monkeypatch.setattr(digest.threading, "Thread", lambda **kw: started.append(kw))
        assert digest.start_digest_scheduler() is False
        assert started == []

    def test_starts_a_daemon_thread(self, monkeypatch):
        made = {}

        class _T:
            def __init__(self, **kw):
                made.update(kw)

            def start(self):
                made["started"] = True

        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.test/h")
        monkeypatch.delenv("HOV_ANALYTICS_INTERVAL_HOURS", raising=False)
        monkeypatch.setattr(digest.threading, "Thread", _T)
        assert digest.start_digest_scheduler() is True
        assert made["daemon"] is True
        assert made["started"] is True

    def test_starting_twice_only_makes_one_thread(self, monkeypatch):
        count = []

        class _T:
            def __init__(self, **kw):
                count.append(1)

            def start(self):
                pass

        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.test/h")
        monkeypatch.setattr(digest.threading, "Thread", _T)
        digest.start_digest_scheduler()
        digest.start_digest_scheduler()
        assert len(count) == 1

    def test_bad_interval_falls_back_to_the_default(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_INTERVAL_HOURS", "not-a-number")
        assert digest._interval_seconds() == 24 * 3600

    def test_interval_is_configurable(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_INTERVAL_HOURS", "6")
        assert digest._interval_seconds() == 6 * 3600
