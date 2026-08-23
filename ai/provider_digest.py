"""Discord digest of LLM provider usage and free-tier headroom.

Companion to the per-call `[LLM SATURATION]` line in ``ai/llm_client.py``: that
one is for tailing a log during development, this one is for knowing after
deployment — without watching anything — that the game is about to run out of
free inference.

Shaped after the Chester project's weekly analytics report so the two read
alike: an embed posted to an incoming webhook, a quiet skip when no webhook is
configured, and a snapshot-and-reset so each digest covers exactly one window.

Configuration:
    HOV_ANALYTICS_WEBHOOK_URL   Discord incoming webhook. Unset = feature off,
                                and no scheduler thread is started at all.
    HOV_ANALYTICS_SECTIONS      Comma-separated subset of the section keys in
                                ``SECTIONS`` (default: all, in listed order).
    HOV_ANALYTICS_INTERVAL_HOURS
                                Routine cadence (default 168 = weekly; 0 off).
    HOV_ANALYTICS_ALERT_INTERVAL_HOURS
                                Cadence while headroom is low (default 1).
    HOV_ANALYTICS_ALERT_THRESHOLD
                                Saturation that escalates to the alert cadence
                                (default 0.75; "75" is read as 75%). Measured
                                against the LEAST saturated provider, so it
                                trips only when every reporting provider is
                                that spent — one host with room means the
                                chain is fine.

Deliberately its own module rather than more surface on the adapter: nothing
here is on the inference path, and a webhook failure must never be able to cost
a player their conversation turn.
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from ai.llm_client import GenericLLMClient

logger = logging.getLogger(__name__)

WEBHOOK_ENV = "HOV_ANALYTICS_WEBHOOK_URL"
SECTIONS_ENV = "HOV_ANALYTICS_SECTIONS"
INTERVAL_ENV = "HOV_ANALYTICS_INTERVAL_HOURS"
ALERT_INTERVAL_ENV = "HOV_ANALYTICS_ALERT_INTERVAL_HOURS"
ALERT_THRESHOLD_ENV = "HOV_ANALYTICS_ALERT_THRESHOLD"

# Routine cadence: a weekly note that everything is fine. The alert cadence
# takes over while the chain is running low, because a weekly digest reporting
# that inference died on Tuesday is of no use on Sunday.
DEFAULT_INTERVAL_HOURS = 168
DEFAULT_ALERT_INTERVAL_HOURS = 1
DEFAULT_ALERT_THRESHOLD = 0.75

# How often the scheduler re-checks saturation while waiting. Small enough that
# a rise mid-wait escalates promptly, large enough to cost nothing.
SCHEDULER_TICK_SECONDS = 60

# How soon to retry after Discord rejects a digest. Without this a single
# transient blip would push the next attempt a full cadence away — a week, on
# the routine schedule — even though the window is still sitting there unsent.
SEND_RETRY_BACKOFF_SECONDS = 300

# Set once the background scheduler is running, so repeated calls from the
# prewarm path (which fires on world loads) cannot stack up threads.
_scheduler_started = False

# Discord blurple, matching Chester's report; red for a low-headroom alert so
# the escalated digests are distinguishable at a glance in the channel.
EMBED_COLOR = 0x5865F2
ALERT_COLOR = 0xED4245
POST_TIMEOUT_SECONDS = 10

# Section keys in default render order.
SECTIONS = ("saturation", "traffic", "reliability")


def _pct(value: Optional[float]) -> str:
    return "unknown" if value is None else "%.0f%%" % (value * 100)


def format_saturation(snapshot: Dict[str, Any]) -> str:
    """Per-provider headroom, worst first — the reason this digest exists."""
    providers = snapshot.get("providers") or {}
    if not providers:
        return "No provider calls recorded this window."

    def key(item):
        saturation = item[1].get("saturation")
        # Worst first; providers that reported nothing sort last, since an
        # unknown is not a warning and should not head the list.
        return (1.0 if saturation is None else -saturation, item[0])

    lines = []
    for name, stats in sorted(providers.items(), key=key):
        saturation = stats.get("saturation")
        line = "`%s` — %s used" % (name, _pct(saturation))
        if stats.get("limit") is not None:
            line += " (%g/%g %s left" % (
                stats.get("remaining"),
                stats.get("limit"),
                stats.get("dimension") or "units",
            )
            reset = stats.get("reset")
            line += ", resets %s)" % GenericLLMClient._format_reset(reset) if reset else ")"
        if saturation is not None and saturation >= 1.0:
            line += " **EXHAUSTED**"
        lines.append(line)

    total = snapshot.get("total_saturation")
    lines.append(
        "\n**Effective: %s** (%d of %d reporting providers exhausted)"
        % (
            _pct(total),
            snapshot.get("providers_exhausted", 0),
            snapshot.get("providers_reporting", 0),
        )
    )
    return "\n".join(lines)


def format_traffic(snapshot: Dict[str, Any]) -> str:
    """Where the calls actually went this window."""
    providers = snapshot.get("providers") or {}
    total = sum(s.get("requests", 0) for s in providers.values())
    if not total:
        return "No calls this window."
    lines = []
    for name, stats in sorted(
        providers.items(), key=lambda kv: -kv[1].get("requests", 0)
    ):
        requests_made = stats.get("requests", 0)
        if not requests_made:
            continue
        share = requests_made / total * 100
        lines.append("`%s`: %d call(s), %.0f%%" % (name, requests_made, share))
    return "\n".join(lines) or "No calls this window."


def format_reliability(snapshot: Dict[str, Any]) -> str:
    """Success rate, rate limiting, and other failures per provider."""
    providers = snapshot.get("providers") or {}
    rows = []
    for name, stats in sorted(providers.items()):
        attempted = stats.get("requests", 0)
        if not attempted:
            continue
        ok = stats.get("successes", 0)
        rows.append(
            "`%s`: %.0f%% success (%d/%d), %d rate-limited, %d error(s)"
            % (
                name,
                ok / attempted * 100,
                ok,
                attempted,
                stats.get("rate_limited", 0),
                stats.get("errors", 0),
            )
        )
    return "\n".join(rows) or "No calls this window."


_FORMATTERS = {
    "saturation": ("📉 Free-Tier Saturation", format_saturation),
    "traffic": ("🔀 Provider Traffic", format_traffic),
    "reliability": ("🩺 Reliability", format_reliability),
}


def _enabled_sections() -> List[str]:
    """Section keys to render, honouring HOV_ANALYTICS_SECTIONS."""
    raw = os.getenv(SECTIONS_ENV, "").strip()
    if not raw:
        return list(SECTIONS)
    wanted = [s.strip().lower() for s in raw.split(",") if s.strip()]
    chosen = [s for s in SECTIONS if s in wanted]
    return chosen or list(SECTIONS)


def build_digest(snapshot: Dict[str, Any], alert: bool = False) -> Dict[str, Any]:
    """Build the Discord embed for one usage window.

    ``alert`` marks a digest sent on the escalated cadence, so a reader can tell
    an hourly "we are running out" from the routine weekly note without doing
    the arithmetic themselves.
    """
    window_start = snapshot.get("window_start")
    if isinstance(window_start, datetime):
        window_text = window_start.strftime("%Y-%m-%d %H:%MZ")
    else:
        window_text = "unknown"

    fields = []
    for key in _enabled_sections():
        name, formatter = _FORMATTERS[key]
        try:
            value = formatter(snapshot)
        except Exception as e:  # a broken section must not lose the digest
            logger.warning("Digest section %s failed: %s", key, e)
            value = "unavailable"
        # Discord caps a field value at 1024 characters.
        fields.append({"name": name, "value": value[:1024] or "—", "inline": False})

    description = "Window: %s → %s" % (
        window_text,
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ"),
    )
    if alert:
        banner = (
            "⚠️ **Low headroom** — every reporting provider is at least %.0f%% "
            "spent, so digests run every %.1fh until that clears."
            % (_alert_threshold() * 100, _alert_interval_seconds() / 3600.0)
        )
        description = banner + "\n\n" + description

    return {
        "title": "🧠 Heart of Virtue — LLM Provider Digest",
        "description": description,
        "color": ALERT_COLOR if alert else EMBED_COLOR,
        "fields": fields,
        "footer": {"text": "Heart of Virtue • LLM provider analytics"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _hours_env(name: str, default_hours: float) -> int:
    """Read an hours-valued env var into seconds.

    A non-numeric value falls back to the default rather than disabling the
    feature silently — a typo in a .env should not quietly stop the reporting
    that exists to tell you something is wrong.
    """
    raw = os.getenv(name, "").strip()
    if not raw:
        return int(default_hours * 3600)
    try:
        hours = float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "%s=%r is not a number; using the %gh default.", name, raw, default_hours
        )
        return int(default_hours * 3600)
    return int(hours * 3600)


def _baseline_interval_seconds() -> int:
    """Routine cadence — weekly unless configured otherwise."""
    return _hours_env(INTERVAL_ENV, DEFAULT_INTERVAL_HOURS)


def _alert_interval_seconds() -> int:
    """Cadence while headroom is low — hourly unless configured otherwise."""
    return _hours_env(ALERT_INTERVAL_ENV, DEFAULT_ALERT_INTERVAL_HOURS)


def _alert_threshold() -> float:
    """Saturation at or above which the digest escalates to the alert cadence."""
    raw = os.getenv(ALERT_THRESHOLD_ENV, "").strip()
    if not raw:
        return DEFAULT_ALERT_THRESHOLD
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "%s=%r is not a number; using %g.",
            ALERT_THRESHOLD_ENV, raw, DEFAULT_ALERT_THRESHOLD,
        )
        return DEFAULT_ALERT_THRESHOLD
    # The digest renders this as a percentage, so "75" is the obvious thing to
    # write here. Taken literally it would exceed any possible saturation and
    # silently disable the alert cadence, so read it as the percentage it is.
    if value > 1:
        value /= 100.0
    return min(max(value, 0.0), 1.0)


def _should_alert() -> bool:
    """True when the chain as a whole is short of headroom.

    Keyed on ``total_saturation``, which is the *least* saturated provider that
    reported a limit: one host with room means the chain is fine no matter how
    spent the others are, and conversely crossing this line means even the
    best-placed provider is nearly out. None (nobody reported a limit) is not an
    alert — an unknown is not bad news.
    """
    total = GenericLLMClient.provider_saturation().get("total_saturation")
    return total is not None and total >= _alert_threshold()


def _required_interval_seconds() -> int:
    """The cadence that currently applies, alert or routine."""
    return _alert_interval_seconds() if _should_alert() else _baseline_interval_seconds()


def _send_due(elapsed_seconds: float) -> bool:
    """Whether a digest is due after waiting ``elapsed_seconds``.

    Re-evaluated every tick rather than fixed when the wait began, so saturation
    rising two days into a weekly wait fires the digest immediately instead of
    five days late.
    """
    return elapsed_seconds >= _required_interval_seconds()


def _elapsed_after_attempt(sent: bool) -> float:
    """Where the wait counter resumes after a send attempt.

    A successful post starts the next window from zero. A failed one resumes
    close to due, so the retry lands in ``SEND_RETRY_BACKOFF_SECONDS`` rather
    than a full cadence later — the window is still open and still unsent.
    """
    if sent:
        return 0.0
    return max(0.0, _required_interval_seconds() - SEND_RETRY_BACKOFF_SECONDS)


def start_digest_scheduler() -> bool:
    """Start the background digest thread, if it is configured and not running.

    Mirrors ``_start_nightly_refresh`` in ``ai/llm_client.py``: a daemon thread
    guarded by a module-level flag, so the prewarm path can call it on every
    world load without stacking threads. Returns True only when a thread was
    actually started.

    Setting the interval to 0 disables it, as does leaving the webhook unset —
    in both cases nothing is spawned at all.
    """
    global _scheduler_started
    if _scheduler_started:
        return False
    if not os.getenv(WEBHOOK_ENV, "").strip():
        logger.info("%s is not set — provider digest scheduler not started.", WEBHOOK_ENV)
        return False
    if _baseline_interval_seconds() <= 0:
        logger.info("%s disables the provider digest scheduler.", INTERVAL_ENV)
        return False

    def _digest_loop():
        # Wait in short ticks rather than one long sleep: the cadence is not
        # fixed when the wait begins, so saturation rising two days into a
        # weekly wait escalates immediately instead of five days late.
        elapsed = 0.0
        while True:
            time.sleep(SCHEDULER_TICK_SECONDS)
            elapsed += SCHEDULER_TICK_SECONDS
            try:
                if _send_due(elapsed):
                    elapsed = _elapsed_after_attempt(send_digest())
            except Exception as e:  # send_digest already swallows; belt and braces
                logger.warning("Provider digest loop error: %s", e)
                elapsed = _elapsed_after_attempt(False)

    thread = threading.Thread(
        target=_digest_loop, daemon=True, name="llm-provider-digest"
    )
    thread.start()
    # Only claim the scheduler is running once it actually is — setting this
    # first would permanently block retries if the thread failed to spawn.
    _scheduler_started = True
    logger.info(
        "Provider digest scheduler started (routine every %.1fh, %.1fh while "
        "saturation is at or above %.0f%%).",
        _baseline_interval_seconds() / 3600.0,
        _alert_interval_seconds() / 3600.0,
        _alert_threshold() * 100,
    )
    return True


def send_digest() -> bool:
    """Post the current window to Discord and start a new one.

    Returns True only when Discord accepted the post. Never raises: this runs
    beside gameplay, and an analytics failure is not worth a turn. The window
    is rolled over only on success, so a failed post costs a digest rather than
    the traffic it was meant to describe.
    """
    webhook = os.getenv(WEBHOOK_ENV, "").strip()
    if not webhook:
        logger.info("%s is not set — skipping the provider digest.", WEBHOOK_ENV)
        return False

    # Read first, reset only once Discord has the numbers. Zeroing up front
    # would mean a Discord outage silently destroyed the window it failed to
    # report; leaving it open instead rolls that traffic into the next digest.
    snapshot = GenericLLMClient.usage_snapshot()
    alert = _should_alert()
    try:
        embed = build_digest(snapshot, alert=alert)
        response = requests.post(
            webhook,
            json={"embeds": [embed]},
            headers={"Content-Type": "application/json"},
            timeout=POST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except Exception as e:
        logger.warning(
            "Provider digest post failed, keeping the window open: %s", e
        )
        return False
    GenericLLMClient.reset_usage_window()
    logger.info("Provider digest posted to Discord.")
    return True
