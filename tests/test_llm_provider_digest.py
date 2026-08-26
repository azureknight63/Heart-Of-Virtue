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

        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.com/api/webhooks/1/test-hook")
        monkeypatch.setattr(digest.requests, "post", fake_post)
        _record("groq", 100, 50)

        assert digest.send_digest() is True
        assert sent["url"] == "https://discord.com/api/webhooks/1/test-hook"
        assert "embeds" in sent["json"]
        assert len(sent["json"]["embeds"]) == 1

    def test_a_failed_post_does_not_raise(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("discord is down")

        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.com/api/webhooks/1/test-hook")
        monkeypatch.setattr(digest.requests, "post", boom)
        assert digest.send_digest() is False

    def test_http_error_does_not_raise(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.com/api/webhooks/1/test-hook")
        monkeypatch.setattr(digest.requests, "post", lambda *a, **k: _Resp(500))
        assert digest.send_digest() is False

    def test_a_failed_post_keeps_the_window_open(self, monkeypatch):
        """An outage costs a digest, not the traffic it was describing."""
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.com/api/webhooks/1/test-hook")
        monkeypatch.setattr(digest.requests, "post", lambda *a, **k: _Resp(500))
        _record("groq", 100, 50)
        assert digest.send_digest() is False
        providers = GenericLLMClient.provider_saturation()["providers"]
        assert providers["groq"]["requests"] == 1

    def test_sending_resets_the_window(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.com/api/webhooks/1/test-hook")
        monkeypatch.setattr(digest.requests, "post", lambda *a, **k: _Resp())
        _record("groq", 100, 50)
        digest.send_digest()
        assert GenericLLMClient.provider_saturation()["providers"]["groq"]["requests"] == 0

    def test_failure_log_does_not_leak_the_webhook_url(self, monkeypatch, caplog):
        """A requests exception's str() embeds the full request URL -- a
        bearer credential for an incoming webhook. The failure log must never
        interpolate it, only the exception type and (if present) status."""
        webhook = "https://discord.com/api/webhooks/1/test-hook"

        class _LeakyError(RuntimeError):
            pass

        def boom(*a, **k):
            # Stands in for requests.exceptions.RequestException, whose
            # message embeds the request (and, for HTTPError, the response).
            raise _LeakyError("POST %s failed: 429 Too Many Requests" % webhook)

        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", webhook)
        monkeypatch.setattr(digest.requests, "post", boom)
        with caplog.at_level("WARNING"):
            assert digest.send_digest() is False
        logged = "\n".join(r.getMessage() for r in caplog.records)
        assert webhook not in logged
        assert "_LeakyError" in logged

    def test_failed_post_does_not_lose_usage_for_the_next_digest(self, monkeypatch):
        """Counts recorded during a failed post must show up in the next one,
        not vanish -- see the ``merge_usage`` call in ``send_digest``."""
        webhook = "https://discord.com/api/webhooks/1/test-hook"
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", webhook)

        calls = {"n": 0}
        posted = []

        def flaky_post(url, json=None, headers=None, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return _Resp(500)
            posted.append(json)
            return _Resp()

        monkeypatch.setattr(digest.requests, "post", flaky_post)

        _record("groq", 100, 50)
        assert digest.send_digest() is False
        # Not lost: visible in the live window immediately after the failure.
        assert GenericLLMClient.provider_saturation()["providers"]["groq"]["requests"] == 1

        _record("groq", 100, 49)
        assert digest.send_digest() is True
        blob = str(posted[0])
        assert "2 call(s)" in blob  # the failed attempt's call plus this one

    def test_call_recorded_during_a_failed_post_is_not_lost(self, monkeypatch):
        """A call landing while the POST is still in flight lands in the new
        (already-reset) window and must survive the merge-back on failure."""
        webhook = "https://discord.com/api/webhooks/1/test-hook"
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", webhook)

        def flaky_post(url, json=None, headers=None, timeout=None):
            _record("groq", 100, 40)  # a call landing mid-POST
            return _Resp(500)

        monkeypatch.setattr(digest.requests, "post", flaky_post)
        _record("groq", 100, 50)  # a call recorded before send_digest started

        assert digest.send_digest() is False
        assert GenericLLMClient.provider_saturation()["providers"]["groq"]["requests"] == 2


class _FakeThreading:
    """Stand-in for the threading module.

    Patching ``digest.threading.Thread`` would mutate the real threading module
    process-wide for the duration of the test; swapping the module reference the
    code actually looks through keeps the blast radius inside this test.
    """

    def __init__(self, record=None, thread_cls=None):
        self._record = record
        self._thread_cls = thread_cls

    def Thread(self, **kwargs):
        if self._record is not None:
            self._record.append(kwargs)
        if self._thread_cls is not None:
            return self._thread_cls(**kwargs)
        return _NullThread()


class _NullThread:
    def start(self):
        pass


class TestDigestScheduler:
    """The digest is worthless if nothing ever fires it."""

    def setup_method(self):
        digest._scheduler_started = False

    def teardown_method(self):
        digest._scheduler_started = False

    def test_no_webhook_means_no_thread(self, monkeypatch):
        started = []
        monkeypatch.delenv("HOV_ANALYTICS_WEBHOOK_URL", raising=False)
        monkeypatch.setattr(digest, "threading", _FakeThreading(started))
        assert digest.start_digest_scheduler() is False
        assert started == []

    def test_zero_interval_disables_it(self, monkeypatch):
        started = []
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.com/api/webhooks/1/test-h")
        monkeypatch.setenv("HOV_ANALYTICS_INTERVAL_HOURS", "0")
        monkeypatch.setattr(digest, "threading", _FakeThreading(started))
        assert digest.start_digest_scheduler() is False
        assert started == []

    def test_starts_a_daemon_thread(self, monkeypatch):
        made = {}

        class _T:
            def __init__(self, **kw):
                made.update(kw)

            def start(self):
                made["started"] = True

        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.com/api/webhooks/1/test-h")
        monkeypatch.delenv("HOV_ANALYTICS_INTERVAL_HOURS", raising=False)
        monkeypatch.setattr(digest, "threading", _FakeThreading(thread_cls=_T))
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

        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.com/api/webhooks/1/test-h")
        monkeypatch.setattr(digest, "threading", _FakeThreading(thread_cls=_T))
        digest.start_digest_scheduler()
        digest.start_digest_scheduler()
        assert len(count) == 1

    def test_bad_interval_falls_back_to_the_default(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_INTERVAL_HOURS", "not-a-number")
        assert digest._baseline_interval_seconds() == 168 * 3600


class TestWebhookValidation:
    """The webhook must be an https:// discord.com/discordapp.com URL, or a
    copy-paste mistake could turn this into a beacon for an arbitrary host."""

    def setup_method(self):
        digest._scheduler_started = False

    def teardown_method(self):
        digest._scheduler_started = False

    def test_discord_com_is_valid(self):
        assert digest._webhook_url_is_valid(
            "https://discord.com/api/webhooks/1/tok"
        ) is True

    def test_discordapp_com_is_valid(self):
        assert digest._webhook_url_is_valid(
            "https://discordapp.com/api/webhooks/1/tok"
        ) is True

    def test_subdomain_is_allowed(self):
        assert digest._webhook_url_is_valid(
            "https://canary.discordapp.com/api/webhooks/1/tok"
        ) is True

    def test_http_scheme_is_rejected(self):
        assert digest._webhook_url_is_valid(
            "http://discord.com/api/webhooks/1/tok"
        ) is False

    def test_non_discord_host_is_rejected(self):
        assert digest._webhook_url_is_valid("https://evil.example/steal") is False

    def test_lookalike_host_is_rejected(self):
        """``discord.com.evil.example`` must not pass a naive suffix check."""
        assert digest._webhook_url_is_valid(
            "https://discord.com.evil.example/hook"
        ) is False

    def test_garbage_url_is_rejected(self):
        assert digest._webhook_url_is_valid("not a url") is False

    def test_send_digest_treats_a_bad_host_as_unset(self, monkeypatch):
        posted = []
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://evil.example/steal")
        monkeypatch.setattr(digest.requests, "post", lambda *a, **k: posted.append(1))
        assert digest.send_digest() is False
        assert posted == []

    def test_scheduler_treats_a_bad_host_as_unset(self, monkeypatch):
        started = []
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://evil.example/steal")
        monkeypatch.setattr(digest, "threading", _FakeThreading(started))
        assert digest.start_digest_scheduler() is False
        assert started == []


class TestAdaptiveCadence:
    """Weekly normally; hourly while the chain is running out of headroom.

    total_saturation is the *least* saturated reporting provider, so crossing
    the alert threshold means even the best-off provider is that far spent —
    i.e. the whole chain is close to silent, which is exactly when a weekly
    digest arrives too late to act on.
    """

    def setup_method(self):
        GenericLLMClient.reset_class_state()

    def teardown_method(self):
        GenericLLMClient.reset_class_state()

    def _saturate(self, provider, limit, remaining):
        GenericLLMClient._record_provider_usage(
            provider,
            _HeaderResp(
                {
                    "x-ratelimit-limit": str(limit),
                    "x-ratelimit-remaining": str(remaining),
                }
            ),
        )

    def test_baseline_is_weekly(self, monkeypatch):
        monkeypatch.delenv("HOV_ANALYTICS_INTERVAL_HOURS", raising=False)
        assert digest._baseline_interval_seconds() == 168 * 3600

    def test_alert_cadence_is_hourly(self, monkeypatch):
        monkeypatch.delenv("HOV_ANALYTICS_ALERT_INTERVAL_HOURS", raising=False)
        assert digest._alert_interval_seconds() == 3600

    def test_threshold_defaults_to_75_percent(self, monkeypatch):
        monkeypatch.delenv("HOV_ANALYTICS_ALERT_THRESHOLD", raising=False)
        assert digest._alert_threshold() == 0.75

    def test_both_cadences_are_configurable(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_INTERVAL_HOURS", "72")
        monkeypatch.setenv("HOV_ANALYTICS_ALERT_INTERVAL_HOURS", "0.5")
        assert digest._baseline_interval_seconds() == 72 * 3600
        assert digest._alert_interval_seconds() == 1800

    def test_alert_interval_zero_means_no_escalation_not_every_tick(self, monkeypatch):
        """0 here is not the same 0 as HOV_ANALYTICS_INTERVAL_HOURS=0: that one
        disables the feature outright, this one just declines to speed up."""
        monkeypatch.setenv("HOV_ANALYTICS_INTERVAL_HOURS", "72")
        monkeypatch.setenv("HOV_ANALYTICS_ALERT_INTERVAL_HOURS", "0")
        assert digest._alert_interval_seconds() == 72 * 3600

    def test_negative_alert_interval_also_falls_back_to_baseline(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_INTERVAL_HOURS", "72")
        monkeypatch.setenv("HOV_ANALYTICS_ALERT_INTERVAL_HOURS", "-3")
        assert digest._alert_interval_seconds() == 72 * 3600

    def test_required_interval_does_not_collapse_to_every_tick_while_saturated(
        self, monkeypatch
    ):
        """A saturated chain with the alert cadence disabled must keep the
        routine cadence, not fire a digest on every SCHEDULER_TICK_SECONDS."""
        monkeypatch.setenv("HOV_ANALYTICS_ALERT_INTERVAL_HOURS", "0")
        self._saturate("groq", 100, 5)  # saturated -- would normally escalate
        assert digest._should_alert() is True
        assert digest._required_interval_seconds() == digest._baseline_interval_seconds()

    def test_no_alert_with_headroom(self):
        self._saturate("groq", 100, 90)  # 10% used
        assert digest._should_alert() is False

    def test_alert_once_past_the_threshold(self):
        self._saturate("groq", 100, 20)  # 80% used
        assert digest._should_alert() is True

    def test_threshold_is_inclusive(self):
        self._saturate("groq", 100, 25)  # exactly 75%
        assert digest._should_alert() is True

    def test_a_single_spare_provider_keeps_the_alert_off(self):
        """Headroom anywhere means the chain is fine, however bad the rest are."""
        self._saturate("openrouter", 50, 0)  # exhausted
        self._saturate("groq", 100, 95)  # 5% used
        assert digest._should_alert() is False

    def test_no_reported_limits_means_no_alert(self):
        GenericLLMClient._record_provider_usage("groq", _HeaderResp({}))
        assert digest._should_alert() is False

    def test_required_interval_switches_with_saturation(self):
        self._saturate("groq", 100, 90)
        assert digest._required_interval_seconds() == 168 * 3600
        self._saturate("groq", 100, 5)
        assert digest._required_interval_seconds() == 3600

    def test_send_is_not_due_before_the_interval(self):
        self._saturate("groq", 100, 90)
        assert digest._send_due(3600) is False

    def test_send_is_due_after_the_interval(self):
        self._saturate("groq", 100, 90)
        assert digest._send_due(168 * 3600) is True

    def test_rising_saturation_makes_a_pending_wait_due_immediately(self):
        """Two days into a weekly wait, crossing 75% should fire now."""
        two_days = 48 * 3600
        self._saturate("groq", 100, 90)
        assert digest._send_due(two_days) is False
        self._saturate("groq", 100, 10)  # 90% used
        assert digest._send_due(two_days) is True


class TestAlertDigestIsMarked:
    def setup_method(self):
        GenericLLMClient.reset_class_state()

    def teardown_method(self):
        GenericLLMClient.reset_class_state()

    def test_routine_digest_is_not_flagged(self):
        embed = digest.build_digest(GenericLLMClient.usage_snapshot(), alert=False)
        assert "Low headroom" not in str(embed)
        assert embed["color"] == digest.EMBED_COLOR

    def test_alert_digest_says_why_it_arrived(self):
        embed = digest.build_digest(GenericLLMClient.usage_snapshot(), alert=True)
        assert "headroom" in str(embed).lower()
        assert embed["color"] == digest.ALERT_COLOR

    def test_send_digest_marks_the_alert(self, monkeypatch):
        sent = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            sent["json"] = json
            return _Resp()

        GenericLLMClient._record_provider_usage(
            "groq", _HeaderResp({"x-ratelimit-limit": "100", "x-ratelimit-remaining": "5"})
        )
        monkeypatch.setenv("HOV_ANALYTICS_WEBHOOK_URL", "https://discord.com/api/webhooks/1/test-h")
        monkeypatch.setattr(digest.requests, "post", fake_post)
        digest.send_digest()
        assert sent["json"]["embeds"][0]["color"] == digest.ALERT_COLOR


class TestRetryBackoff:
    """A Discord blip must not cost a full cadence of silence."""

    def setup_method(self):
        GenericLLMClient.reset_class_state()

    def teardown_method(self):
        GenericLLMClient.reset_class_state()

    def test_success_starts_the_next_window_from_zero(self):
        assert digest._elapsed_after_attempt(True) == 0.0

    def test_failure_resumes_close_to_due(self):
        resumed = digest._elapsed_after_attempt(False)
        assert resumed == 168 * 3600 - digest.SEND_RETRY_BACKOFF_SECONDS
        # i.e. the retry lands one backoff from now, not one week.
        assert digest._send_due(resumed + digest.SEND_RETRY_BACKOFF_SECONDS) is True
        assert digest._send_due(resumed) is False

    def test_failure_during_an_alert_retries_within_the_alert_cadence(self):
        GenericLLMClient._record_provider_usage(
            "groq",
            _HeaderResp({"x-ratelimit-limit": "100", "x-ratelimit-remaining": "5"}),
        )
        resumed = digest._elapsed_after_attempt(False)
        assert resumed == 3600 - digest.SEND_RETRY_BACKOFF_SECONDS

    def test_backoff_never_goes_negative(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_ALERT_INTERVAL_HOURS", "0.01")
        GenericLLMClient._record_provider_usage(
            "groq",
            _HeaderResp({"x-ratelimit-limit": "100", "x-ratelimit-remaining": "5"}),
        )
        assert digest._elapsed_after_attempt(False) == 0.0


class TestThresholdIsForgiving:
    """The digest prints a percentage, so someone will write one here."""

    def test_percentage_form_is_understood(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_ALERT_THRESHOLD", "75")
        assert digest._alert_threshold() == 0.75

    def test_fraction_form_still_works(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_ALERT_THRESHOLD", "0.6")
        assert digest._alert_threshold() == 0.6

    def test_out_of_range_is_clamped(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_ALERT_THRESHOLD", "-5")
        assert digest._alert_threshold() == 0.0

    def test_alert_still_fires_with_the_percentage_form(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_ALERT_THRESHOLD", "75")
        GenericLLMClient._record_provider_usage(
            "groq",
            _HeaderResp({"x-ratelimit-limit": "100", "x-ratelimit-remaining": "10"}),
        )
        assert digest._should_alert() is True
        GenericLLMClient.reset_class_state()


class TestAlertBannerMatchesConfig:
    def test_banner_quotes_the_configured_cadence(self, monkeypatch):
        monkeypatch.setenv("HOV_ANALYTICS_ALERT_INTERVAL_HOURS", "3")
        embed = digest.build_digest(GenericLLMClient.usage_snapshot(), alert=True)
        assert "3.0h" in embed["description"]
