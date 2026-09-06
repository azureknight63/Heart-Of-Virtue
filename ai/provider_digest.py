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

The webhook must be an ``https://`` URL on ``discord.com`` or
``discordapp.com`` (subdomains allowed); anything else is treated as unset,
since posting analytics to an arbitrary URL is a credential leak waiting to
happen, not a feature.

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
from urllib.parse import urlparse

import requests

from ai.llm_client import GenericLLMClient
from src.text_format import pct

logger = logging.getLogger(__name__)

WEBHOOK_ENV = "HOV_ANALYTICS_WEBHOOK_URL"
SECTIONS_ENV = "HOV_ANALYTICS_SECTIONS"
INTERVAL_ENV = "HOV_ANALYTICS_INTERVAL_HOURS"
ALERT_INTERVAL_ENV = "HOV_ANALYTICS_ALERT_INTERVAL_HOURS"
ALERT_THRESHOLD_ENV = "HOV_ANALYTICS_ALERT_THRESHOLD"

# Hosts the webhook URL is allowed to point at, plus their subdomains (Discord
# serves webhooks from region/canary subdomains of both).
ALLOWED_WEBHOOK_HOSTS = ("discord.com", "discordapp.com")

# Routine cadence: a weekly note that everything is fine. The alert cadence
# takes over while the chain is running low, because a weekly digest reporting
# that inference died on Tuesday is of no use on Sunday.
DEFAULT_INTERVAL_HOURS = 168
DEFAULT_ALERT_INTERVAL_HOURS = 1
DEFAULT_ALERT_THRESHOLD = 0.75

# How often the scheduler re-checks saturation while waiting. Small enough that
# a rise mid-wait escalates promptly, large enough to cost nothing.
SCHEDULER_TICK_SECONDS = 60

# How much slack the usage window gets over the digest cadence before
# llm_client's own auto-roll is allowed to end it.
#
# It has to be strictly greater than 1. The scheduler measures its cadence by
# counting ticks (SCHEDULER_TICK_SECONDS each), and `time.sleep` overshoots, so
# the real elapsed time always runs *ahead* of that counter. With the bound set
# to exactly the cadence, the window therefore goes stale strictly BEFORE
# `_send_due` fires — and any inference call landing in that gap rolls the
# window and zeroes the counters the digest is about to snapshot, so the traffic
# and reliability sections report "No calls this window" for a window that had
# plenty. Doubling it puts the auto-roll where it belongs: a backstop for a
# scheduler that has died, not a race with a scheduler that is working.
WINDOW_SLACK_MULTIPLIER = 2

# How soon to retry after Discord rejects a digest. Without this a single
# transient blip would push the next attempt a full cadence away — a week, on
# the routine schedule — even though the window is still sitting there unsent.
SEND_RETRY_BACKOFF_SECONDS = 300

# Set once this process has SETTLED the scheduling question — thread started,
# or determined not to be wanted. Not "started": latching only the success
# branch left the far commoner unconfigured case (no webhook, which is the
# default) re-taking the lock, re-reading the environment and emitting an INFO
# line on every call, forever — and the prewarm path calls this from a world
# load. Callers still learn whether a thread started from the return value, so
# nothing needs the distinction kept as state.
#
# Configuration is therefore read exactly once per process: a webhook exported
# after the first call is deliberately not picked up. This is boot wiring, not
# a live setting.
#
# Guarded by _scheduler_lock because the prewarm path can run on two concurrent
# world loads (e.g. two players' first requests landing together) — without the
# lock both could read the flag as False and each start a thread.
_scheduler_settled = False
_scheduler_lock = threading.Lock()

# Discord blurple, matching Chester's report; red for a low-headroom alert so
# the escalated digests are distinguishable at a glance in the channel.
EMBED_COLOR = 0x5865F2
ALERT_COLOR = 0xED4245
POST_TIMEOUT_SECONDS = 10

# Section keys in default render order.
SECTIONS = ("saturation", "traffic", "reliability")


def _webhook_url_is_valid(url: str) -> bool:
    """Whether ``url`` is an ``https://`` webhook on an allowed Discord host.

    Not a defense against a malicious operator who controls the environment —
    they could point this at anything regardless. It is a guard against a
    copy-paste mistake (wrong env var, stray placeholder, a URL meant for
    something else entirely) quietly turning this into a beacon that posts
    provider usage data — and, if it were ever misconfigured to also carry a
    query string with a token, worse than that — to an arbitrary endpoint.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return host in ALLOWED_WEBHOOK_HOSTS or any(
        host.endswith("." + allowed) for allowed in ALLOWED_WEBHOOK_HOSTS
    )


def _configured_webhook(action: str) -> Optional[str]:
    """The webhook to post to, or None with a log line saying why not.

    ``start_digest_scheduler`` and ``send_digest`` both have to answer exactly
    this question with exactly these two rejections, and each used to spell out
    its own copy — including its own copy of the message explaining what an
    acceptable URL looks like. ``action`` is the tail of that message
    ("provider digest scheduler not started" / "skipping the provider digest"),
    which is the only part that legitimately differed.
    """
    webhook = os.getenv(WEBHOOK_ENV, "").strip()
    if not webhook:
        logger.info("%s is not set — %s.", WEBHOOK_ENV, action)
        return None
    if not _webhook_url_is_valid(webhook):
        logger.warning(
            "%s is not an https:// discord.com/discordapp.com URL — %s.",
            WEBHOOK_ENV, action,
        )
        return None
    return webhook


def _pct(value: Optional[float]) -> str:
    """``src.text_format.pct``, plus this module's "no data" spelling.

    The third copy of the percentage renderer, written as ``"%.0f%%"`` while
    the other two -- the ones ``src/text_format.py`` was extracted to hold --
    were written as ``int(round(...))``. The two spellings happen to agree on
    every value (both round half to even on the underlying double; a sweep of
    20,001 fractions found no divergence), which is exactly what makes this the
    dangerous kind of duplicate: it reads like a deliberate difference, it
    isn't, and the day someone "fixes" one spelling the digest and the
    ``[LLM SATURATION]`` log line beside it start disagreeing by a point.

    The Optional handling is genuinely local -- nothing else renders a
    percentage that can be absent -- and stays here.
    """
    return "unknown" if value is None else pct(value)


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
        # Shared with llm_client's log_provider_saturation, which renders the
        # same figures from the same record. llm_client owns the format; calling
        # its public method beats re-publishing it under a second module-level
        # name here, which is how one function ends up with two spellings.
        line += GenericLLMClient.format_headroom(stats)
        if saturation is not None and saturation >= 1.0:
            line += " **EXHAUSTED**"
        if stats.get("saturation_inferred"):
            # This figure was guessed from a headerless 429, not reported by
            # the provider. Saying so is the difference between "the day's
            # quota is gone" and "one request bounced off a per-minute bucket",
            # which is the whole decision the reader of this digest is making.
            line += " _(inferred)_"
        lines.append(line)

    effective = snapshot.get("effective_saturation")
    inferred = snapshot.get("providers_exhausted_inferred", 0)
    lines.append(
        "\n**Effective: %s** (%d of %d reporting providers exhausted%s)"
        % (
            _pct(effective),
            snapshot.get("providers_exhausted", 0),
            snapshot.get("providers_reporting", 0),
            ", %d inferred" % inferred if inferred else "",
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


def _hours_env_seconds(name: str, default_hours: float) -> int:
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
    return _hours_env_seconds(INTERVAL_ENV, DEFAULT_INTERVAL_HOURS)


def _alert_interval_seconds() -> int:
    """Cadence while headroom is low — hourly unless configured otherwise.

    Zero or negative does not mean "digest on every scheduler tick" — that
    reading of 0 is reserved for ``HOV_ANALYTICS_INTERVAL_HOURS`` disabling the
    feature entirely (see ``start_digest_scheduler``). Here it means "do not
    escalate", so a saturated chain falls back to the routine cadence instead
    of spamming the channel once a minute.
    """
    seconds = _hours_env_seconds(ALERT_INTERVAL_ENV, DEFAULT_ALERT_INTERVAL_HOURS)
    return seconds if seconds > 0 else _baseline_interval_seconds()


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

    Keyed on ``effective_saturation``, which is the *least* saturated provider
    that reported a limit: one host with room means the chain is fine no matter
    how spent the others are, and conversely crossing this line means even the
    best-placed provider is nearly out. None (nobody reported a limit) is not an
    alert — an unknown is not bad news.
    """
    effective = GenericLLMClient.provider_saturation().get("effective_saturation")
    return effective is not None and effective >= _alert_threshold()


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

    Setting the interval to 0 disables it, as does leaving the webhook unset
    or pointed somewhere other than Discord — in all of those cases nothing is
    spawned at all.

    Genuinely once per process on EVERY path, not just the one that starts a
    thread: each terminal branch latches ``_scheduler_settled``, so a caller on
    a hot route pays one lock acquisition and one environment read for the life
    of the process even in the default no-webhook configuration.

    The whole check-settled / check-configured / start-and-latch sequence runs
    under ``_scheduler_lock`` so two callers racing (e.g. two players' world
    loads landing at once, both calling this from the prewarm path) cannot both
    see the flag as False and each spin up a thread.
    """
    global _scheduler_settled
    with _scheduler_lock:
        if _scheduler_settled:
            return False
        if _configured_webhook("provider digest scheduler not started") is None:
            _scheduler_settled = True
            return False
        if _baseline_interval_seconds() <= 0:
            logger.info("%s disables the provider digest scheduler.", INTERVAL_ENV)
            _scheduler_settled = True
            return False

        # This scheduler now owns the usage window: tell llm_client, whose
        # periodic auto-roll would otherwise cut a weekly digest's span down to
        # a day. Without a digest running that auto-roll is the only thing that
        # ever resets the counters, so it cannot simply be removed — it just has
        # to stay behind this scheduler rather than racing it. See
        # WINDOW_SLACK_MULTIPLIER for why the bound is not the bare cadence.
        GenericLLMClient.set_usage_window_seconds(
            _baseline_interval_seconds() * WINDOW_SLACK_MULTIPLIER
        )

        def _digest_loop():
            # Wait in short ticks rather than one long sleep: the cadence is
            # not fixed when the wait begins, so saturation rising two days
            # into a weekly wait escalates immediately instead of five days
            # late.
            elapsed = 0.0
            while True:
                time.sleep(SCHEDULER_TICK_SECONDS)
                elapsed += SCHEDULER_TICK_SECONDS
                try:
                    if _send_due(elapsed):
                        elapsed = _elapsed_after_attempt(send_digest())
                except Exception:  # send_digest already swallows; belt and braces
                    # Full traceback, unlike send_digest's own handler: the
                    # credential rationale there is about a *requests*
                    # exception carrying the webhook URL, and send_digest never
                    # lets one of those out. Anything reaching here is a bug in
                    # this loop, and a bare exception name is not enough to fix
                    # one in a daemon thread nobody is watching.
                    logger.warning(
                        "Provider digest loop error; retrying.", exc_info=True
                    )
                    elapsed = _elapsed_after_attempt(False)

        thread = threading.Thread(
            target=_digest_loop, daemon=True, name="llm-provider-digest"
        )
        thread.start()
        # Latch only once the thread actually is running: setting this first
        # would permanently block retries if the spawn raised. (An exception
        # from ``start()`` leaves the flag False and the next caller tries
        # again — which is the one case where re-reading the environment is
        # the right thing to do.)
        _scheduler_settled = True
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
    beside gameplay, and an analytics failure is not worth a turn.

    The window is closed by ``snapshot_and_reset()`` *before* the POST, not
    after a successful one: waiting until Discord answers would leave calls
    recorded during the up-to-``POST_TIMEOUT_SECONDS`` request sitting in a
    window that then gets zeroed out from under them by ``reset_usage_window``
    on success, or double-counted by never having moved on failure. Resetting
    first means anything recorded mid-POST simply starts accruing into the
    next window immediately. If the post then fails, the snapshot this digest
    was built from is folded back in with ``merge_usage`` so it is not lost —
    a failed post costs a digest, not the traffic it was meant to describe.
    """
    webhook = _configured_webhook("skipping the provider digest")
    if webhook is None:
        return False

    snap = GenericLLMClient.snapshot_and_reset()
    alert = _should_alert()
    try:
        embed = build_digest(snap, alert=alert)
        response = requests.post(
            webhook,
            json={"embeds": [embed]},
            headers={"Content-Type": "application/json"},
            timeout=POST_TIMEOUT_SECONDS,
            # requests follows redirects by default, which would bind
            # _webhook_url_is_valid's host allow-list to the FIRST hop only: a
            # 302 off a discord.com URL would carry the body anywhere. There is
            # no legitimate redirect on a webhook POST.
            allow_redirects=False,
        )
        response.raise_for_status()
    except Exception as e:
        # Never log str(e) here: for a requests exception that includes the
        # full request (and for an HTTPError, the response too), which embeds
        # the webhook URL — a bearer credential — in stdout/LOG_FILE. Webhook
        # 429s are routine, so this line runs often enough that leaking it
        # once is a certainty, not a risk.
        GenericLLMClient.merge_usage(snap)
        logger.warning(
            "Provider digest post failed: %s status=%s",
            type(e).__name__,
            getattr(getattr(e, "response", None), "status_code", None),
        )
        return False
    logger.info("Provider digest posted to Discord.")
    return True
