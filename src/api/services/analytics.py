"""First-party player analytics.

Gameplay events go to one Turso table, ``analytics_events``, so the maintainer
can answer "how many people are playing, and where do they stop" without a
third-party tracker, a CSP change or a consent banner. The read side (the
reports behind the admin page, the CLI and the Discord digest) is
``analytics_report.py``; this module only writes, and owns the vocabulary both
sides use (``Event``, ``Outcome``, ``ALLOWED_PROPS``).

Three rules shape everything here:

* **Never cost a player a turn.** ``record`` appends to an in-memory buffer; a
  daemon thread flushes it in batches every ``FLUSH_INTERVAL_SECONDS``. Every
  public entry point swallows its own failures (``_best_effort``). A failed
  flush loses that one batch rather than retrying into an outage.
* **Pseudonymous, not raw.** A row carries ``pid``, a keyed hash of the account
  id, and ``sid``, a random per-login id. Never the account id, username,
  email, IP or the session credential, and props are limited to
  ``ALLOWED_PROPS`` so a future call site cannot add one by accident. Turning a
  pid back into an account needs the server's secret. The Privacy Policy
  (TermsOfServiceModal.jsx) describes exactly this; keep the two in step.
* **Off unless configured.** ``src/api/app.py::_init_analytics`` calls
  ``configure``, which enables the recorder only outside TESTING, with a
  database URL and a key, and with ``HOV_ANALYTICS_ENABLED`` not off. The
  recorder is a process-wide singleton, so the last ``create_app`` decides.

Two ways to record, for two situations:

* ``record(event, **props)`` — the usual one. The auth middleware binds the
  request's session (``bind_request_session``), so instrumentation deep in the
  combat adapter or the game service needs no user id threaded through the
  engine. Outside a request, or for a session with no account behind it (the
  ``/api/test/session`` harness bypass), it is a no-op.
* ``recorder.<method>(session, ...)`` — when the caller holds a session the
  request has not bound: sign-in, where the session is created mid-request,
  and the chat routes, whose per-conversation state is keyed by session.

Configuration:
    HOV_ANALYTICS_ENABLED   Read by config.env_flag: blank/0/false/no/off is
                            off. Unset means on.
    HOV_ANALYTICS_SECRET    Key for the pid hash. Unset: a subkey derived from
                            ENCRYPTION_KEY, which production must already set.
                            Changing either re-keys every pid, splitting each
                            player's history, so set it once.
"""

import asyncio
import atexit
import contextlib
import functools
import hashlib
import hmac
import json
import logging
import math
import os
import threading
import time
import uuid
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

from flask import current_app, g, has_request_context, request

from src.api.config import env_flag
from src.api.db import create_client_from_env

logger = logging.getLogger(__name__)

ENABLED_ENV = "HOV_ANALYTICS_ENABLED"
SECRET_ENV = "HOV_ANALYTICS_SECRET"


class Event:
    """Every event name the recorder writes and the reports read."""

    HEARTBEAT = "session.heartbeat"
    LOGIN = "auth.login"
    REGISTER = "auth.register"
    GAME_NEW = "game.new"
    GAME_LOAD = "game.load"
    GAME_SAVE = "game.save"
    PROGRESS_MAP = "progress.map"
    PROGRESS_FLAG = "progress.flag"
    COMBAT_START = "combat.start"
    COMBAT_END = "combat.end"
    CHAT_OPEN = "npc_chat.open"
    CHAT_TURN = "npc_chat.turn"
    CHAT_END = "npc_chat.end"
    FEEDBACK = "feedback.submit"


ALL_EVENTS = frozenset(v for k, v in vars(Event).items() if not k.startswith("_"))
CHAT_EVENTS = (Event.CHAT_OPEN, Event.CHAT_TURN, Event.CHAT_END)


# The label for a name that could not be read: an NPC chat key, or a fight's
# roster (UNKNOWN_ENCOUNTER, before it is known). The reports fall back to it too.
UNKNOWN_LABEL = "unknown"
UNKNOWN_ENCOUNTER = UNKNOWN_LABEL
# The label for a roster that is known and empty.
NO_ENCOUNTER = "none"


class Outcome:
    """How a fight ended: the ``outcome`` prop of ``Event.COMBAT_END``."""

    VICTORY = "victory"
    DEFEAT = "defeat"
    FLEE = "flee"


# The only prop keys a row may carry. A key not listed here is dropped, which
# is what stops a future ``record(..., username=...)`` from writing personal
# data; the reports interpolate these names into SQL, so the list is also what
# keeps that interpolation to known identifiers.
ALLOWED_PROPS = frozenset({
    "abandoned", "beats", "duration_s", "encounter", "flag", "hp_pct",
    "latency_ms", "level", "map", "npc", "outcome", "turns", "type",
})

# One heartbeat per active session per five minutes: fine enough to measure a
# sitting to within five minutes, coarse enough that a busy evening is a few
# hundred rows rather than one per request.
HEARTBEAT_SECONDS = 300

# Only these count as the player doing something. GETs are excluded because the
# client polls combat status every few seconds while a fight is on screen, and
# a tab left open mid-fight is not someone playing.
ACTIVITY_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

FLUSH_INTERVAL_SECONDS = 10

# Bounds one flush, including the one at process exit: an unreachable database
# must not hold up a deploy's restart.
WRITE_TIMEOUT_SECONDS = 10
# Bounds the client close on its own, since after a timed-out write it runs
# where the write's bound no longer reaches.
CLOSE_TIMEOUT_SECONDS = 2

# Caps what one flush interval can queue. Every flush empties the buffer, a
# failed one included (it logs and drops), so this is reached only by more
# than this many events inside FLUSH_INTERVAL_SECONDS.
MAX_BUFFERED_EVENTS = 5000

MAX_PROP_CHARS = 120

# A story event can set a dozen flags in one request; a runaway loop could set
# thousands. Neither is worth thousands of rows.
MAX_FLAGS_PER_OBSERVATION = 25

# The pid is 128 bits of the HMAC: collision-free at any plausible player count,
# and half the row width of the full digest. "pid:" separates this use of the
# key from any other it might be put to.
_PID_DOMAIN = b"pid:"
_PID_HEX_CHARS = 32
# Derives the pid key from ENCRYPTION_KEY rather than using that key directly,
# so the data-encryption key is never itself a MAC key.
_PID_SUBKEY_LABEL = b"hov-analytics-pid-v1"

SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS analytics_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER NOT NULL,
        pid TEXT NOT NULL,
        sid TEXT,
        event TEXT NOT NULL,
        props TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_analytics_event_ts ON analytics_events(event, ts)",
    "CREATE INDEX IF NOT EXISTS idx_analytics_pid_ts ON analytics_events(pid, ts)",
    # The active-player counts filter on time alone.
    "CREATE INDEX IF NOT EXISTS idx_analytics_ts ON analytics_events(ts)",
)

_INSERT_SQL = (
    "INSERT INTO analytics_events (ts, pid, sid, event, props) VALUES (?, ?, ?, ?, ?)"
)

# Per-session analytics state lives in the Session's own __dict__ under this
# key. Sessions are in-memory only and never pickled, so nothing here can leak
# into a save file.
_STATE_KEY = "_analytics"


@dataclass
class _Chat:
    start: float
    turns: int = 0


@dataclass
class _Progress:
    map_name: Optional[str]
    flags: Set[str]


@dataclass
class _SessionState:
    sid: str = field(default_factory=lambda: uuid.uuid4().hex)
    last_beat: Optional[float] = None
    progress: Optional[_Progress] = None
    chats: Dict[str, _Chat] = field(default_factory=dict)


def _sanitize_props(props):
    """Allowed keys only, JSON-safe scalar values, strings clipped."""
    clean = {}
    for key, value in props.items():
        if key not in ALLOWED_PROPS:
            logger.debug("analytics prop %r is not in ALLOWED_PROPS; dropped", key)
        elif isinstance(value, str):
            clean[key] = value[:MAX_PROP_CHARS]
        elif isinstance(value, float) and not math.isfinite(value):
            # json.dumps would write a bare NaN, which SQLite's json functions reject.
            logger.debug("analytics prop %r is not finite; dropped", key)
        elif value is None or isinstance(value, (bool, int, float)):
            clean[key] = value
    return clean


def npc_label(npc_key):
    """The NPC's name from a chat key such as ``Gorran_0``.

    Keys are ``f"{class_name}_{instance_count}"`` (``src/npc/_chat_llm.py``).
    The count is per instance; kept, it would split one NPC's numbers across
    every save that ever met them.
    """
    if not isinstance(npc_key, str) or not npc_key:
        return UNKNOWN_LABEL
    return npc_key.rsplit("_", 1)[0]


def encounter_label(enemies):
    """A stable name for a fight's roster: ``CaveBat+Slime x2``.

    Class names, not display names, so a renamed or randomly named enemy still
    groups with its kind.
    """
    counts = Counter(type(e).__name__ for e in enemies or ())
    if not counts:
        return NO_ENCOUNTER
    return "+".join(
        name if counts[name] == 1 else f"{name} x{counts[name]}" for name in sorted(counts)
    )


def run_with_private_client(work, timeout=None):
    """Run ``await work(client)`` on a private, short-lived libsql client.

    For code outside a request (the flush thread, the CLI, the digest thread).
    Deliberately not ``src.api.db.db``, the client every request shares: a
    slow or unreachable analytics write, bounded here by its own timeouts,
    then never occupies the connection a player's save is waiting on.
    """
    async def _run():
        client = create_client_from_env()
        try:
            return await work(client)
        finally:
            # Bounded on its own: after a timed-out write the close runs
            # inside the cancellation, where the outer bound no longer reaches.
            with contextlib.suppress(Exception):
                await asyncio.wait_for(client.close(), CLOSE_TIMEOUT_SECONDS)

    # A hung write or close would park the flush thread, or the exit-time
    # flush, so both are bounded.
    return asyncio.run(asyncio.wait_for(_run(), timeout) if timeout is not None else _run())


def _turso_writer(statements):
    run_with_private_client(lambda client: client.batch(list(statements)), WRITE_TIMEOUT_SECONDS)


def _best_effort(method):
    """Make a recorder entry point a no-op while disabled, and never raise.

    Analytics must never cost a player a turn: any fault here is logged at
    debug and swallowed.
    """

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.enabled:
            return None
        try:
            return method(self, *args, **kwargs)
        except Exception:
            logger.debug("analytics %s failed", method.__name__, exc_info=True)
            return None

    return wrapper


@contextlib.contextmanager
def _swallowed(label):
    """``_best_effort`` for the module-level helpers: log at debug, never raise."""
    try:
        yield
    except Exception:
        logger.debug("analytics %s failed", label, exc_info=True)


class AnalyticsRecorder:
    """Buffers analytics events and flushes them to the database in batches."""

    def __init__(self, writer=None, clock=time.time, secret=None):
        self.enabled = False
        self._writer = writer or _turso_writer
        self._clock = clock
        self._secret = secret
        self._buffer = deque(maxlen=MAX_BUFFERED_EVENTS)
        # Two locks: _buffer_lock guards the queue, _state_lock the per-session
        # diffs. record() takes the first, so the state methods decide under
        # the second and record after releasing it.
        self._buffer_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._schema_ready = False
        self._warned_full = False
        self._thread = None

    # -- configuration -----------------------------------------------------

    def _pid_key(self):
        """The HMAC key for pids, or None when nothing is configured."""
        secret = self._secret or os.getenv(SECRET_ENV)
        if secret:
            return secret.encode("utf-8")
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if encryption_key:
            return hmac.new(
                encryption_key.encode("utf-8"), _PID_SUBKEY_LABEL, hashlib.sha256
            ).digest()
        return None

    def configure(self, testing, database_url):
        """Decide whether this process records. Returns the decision.

        Sets ``enabled`` on this recorder, which for the module's ``recorder``
        is process-wide: the last ``create_app`` to call it decides.
        """
        self.enabled = bool(
            not testing
            and database_url
            and env_flag(ENABLED_ENV, default=True)
            and self._pid_key()
        )
        return self.enabled

    def pid_for(self, account_id):
        """Keyed hash of an account id: stable per account, opaque without the key.

        Raises when no key is configured rather than hashing with an empty one,
        which anyone could recompute from an account id. (``record`` is best
        effort, so the event is dropped.)
        """
        key = self._pid_key()
        if not key:
            raise RuntimeError("no analytics pid key is configured")
        digest = hmac.new(key, _PID_DOMAIN + str(account_id).encode("utf-8"), hashlib.sha256)
        return digest.hexdigest()[:_PID_HEX_CHARS]

    # -- per-session state -------------------------------------------------

    @staticmethod
    def _state(session):
        """This session's analytics state, created on first use.

        Read through ``vars`` rather than ``getattr`` so a test double that
        answers every attribute cannot invent state or an account id.
        ``setdefault`` so two concurrent first requests share one sid, which is
        also why it needs no lock: callers resolve it before taking
        ``_state_lock``.
        """
        attrs = vars(session)
        state = attrs.get(_STATE_KEY)
        if state is None:
            state = attrs.setdefault(_STATE_KEY, _SessionState())
        return state

    @staticmethod
    def account_id(session):
        """The account behind ``session``, or None for an account-less session."""
        return vars(session).get("db_user_id") if session is not None else None

    # -- writing -----------------------------------------------------------

    @_best_effort
    def record(self, event, session=None, **props):
        """Buffer one event for ``session``."""
        if event not in ALL_EVENTS:
            logger.debug("analytics event %r is not an Event; dropped", event)
            return
        account_id = self.account_id(session)
        if not account_id:
            return
        row = (
            int(self._clock()),
            self.pid_for(account_id),
            self._state(session).sid,
            event,
            json.dumps(_sanitize_props(props), separators=(",", ":")),
        )
        with self._buffer_lock:
            if len(self._buffer) == MAX_BUFFERED_EVENTS and not self._warned_full:
                self._warned_full = True
                logger.warning("Analytics buffer full; the oldest events are being dropped.")
            self._buffer.append(row)

    def flush(self):
        """Write everything buffered. Returns the number of events written."""
        with self._buffer_lock:
            rows = list(self._buffer)
            self._buffer.clear()
            self._warned_full = False
        if not rows:
            return 0
        statements = [] if self._schema_ready else [(s, []) for s in SCHEMA_STATEMENTS]
        statements.extend((_INSERT_SQL, list(row)) for row in rows)
        # Deliberately not @_best_effort: that logs the traceback, and a libsql
        # error can carry the database URL. Only the type is logged here.
        try:
            self._writer(statements)
        except Exception as exc:
            logger.warning(
                "Analytics flush failed (%s); dropped %d events.", type(exc).__name__, len(rows)
            )
            return 0
        self._schema_ready = True
        return len(rows)

    def start(self):
        """Start the flush thread once. Returns True when a thread started."""
        if not self.enabled or self._thread is not None:
            return False
        self._thread = threading.Thread(target=self._flush_forever, name="analytics-flush", daemon=True)
        self._thread.start()
        atexit.register(self.flush)
        logger.info("Analytics recorder started.")
        return True

    def _flush_forever(self, sleep=time.sleep):
        """The flush thread's body: one failed flush must not end recording."""
        while True:
            sleep(FLUSH_INTERVAL_SECONDS)
            with _swallowed("flush"):
                self.flush()

    # -- instrumentation helpers --------------------------------------------

    @_best_effort
    def heartbeat(self, session):
        """Record that ``session`` is active, at most once per HEARTBEAT_SECONDS."""
        if not self.account_id(session):
            return
        state = self._state(session)
        now = self._clock()
        with self._state_lock:
            if state.last_beat is not None and now - state.last_beat < HEARTBEAT_SECONDS:
                return
            state.last_beat = now
        self.record(Event.HEARTBEAT, session)

    @_best_effort
    def reset_progress(self, session, markers):
        """Take a new progress baseline (sign-in, new game, load).

        The current map is recorded, because "reached map X" is counted per
        player and re-recording it is harmless. Existing story flags are not:
        they are where the player already was, not something they just did.
        """
        if not markers:
            return
        map_name = markers.get("map")
        state = self._state(session)
        with self._state_lock:
            state.progress = _Progress(map_name, set(markers.get("flags") or ()))
        if map_name:
            self.record(Event.PROGRESS_MAP, session, map=map_name)

    @_best_effort
    def observe_progress(self, session, markers):
        """Record what changed since the last observation of ``session``."""
        if not markers:
            return
        state = self._state(session)
        with self._state_lock:
            baseline = state.progress
            emits = [] if baseline is None else self._advance_progress(baseline, markers)
        if baseline is None:
            self.reset_progress(session, markers)
            return
        for event, props in emits:
            self.record(event, session, **props)

    @staticmethod
    def _advance_progress(baseline, markers):
        """Events for what ``markers`` adds to ``baseline``; advances the baseline.

        Flags only accumulate: two overlapping requests can observe out of
        order, and replacing the set would let the older one undo the newer and
        re-emit its flags next time. Past ``MAX_FLAGS_PER_OBSERVATION`` in one
        burst, the rest are absorbed unrecorded (see that constant).
        """
        emits = []
        new_map = markers.get("map")
        if new_map and new_map != baseline.map_name:
            emits.append((Event.PROGRESS_MAP, {"map": new_map}))
            baseline.map_name = new_map
        flags = markers.get("flags") or set()
        fresh = sorted(flags - baseline.flags)
        emits.extend((Event.PROGRESS_FLAG, {"flag": f}) for f in fresh[:MAX_FLAGS_PER_OBSERVATION])
        baseline.flags |= flags
        return emits

    @_best_effort
    def chat_opened(self, session, npc_key):
        """A conversation with ``npc_key`` (the server's chat key) began.

        The engine allows one conversation at a time, so any still open (this
        NPC's included: a re-open replaces the earlier conversation, #674) was
        walked away from. It is ended here as ``abandoned`` rather than left
        open forever; the reports keep abandoned conversations out of the
        duration average, since their length is only "until the next open".
        """
        now = self._clock()
        chats = self._state(session).chats
        with self._state_lock:
            abandoned = [(key, chats.pop(key)) for key in list(chats)]
            chats[npc_key] = _Chat(start=now)
        for key, chat in abandoned:
            self._record_chat_end(session, key, chat, now, abandoned=True)
        self.record(Event.CHAT_OPEN, session, npc=npc_label(npc_key))

    @_best_effort
    def chat_turn(self, session, npc_key, latency_ms=None):
        """One reply in an open conversation; ignored if none is open."""
        chats = self._state(session).chats
        with self._state_lock:
            chat = chats.get(npc_key)
            if chat is None:
                return
            chat.turns += 1
        self.record(Event.CHAT_TURN, session, npc=npc_label(npc_key), latency_ms=latency_ms)

    @_best_effort
    def chat_ended(self, session, npc_key):
        """The conversation with ``npc_key`` closed; a no-op when none is open."""
        chats = self._state(session).chats
        with self._state_lock:
            chat = chats.pop(npc_key, None)
        if chat is not None:
            self._record_chat_end(session, npc_key, chat, self._clock())

    def _record_chat_end(self, session, npc_key, chat, now, abandoned=False):
        props = {"npc": npc_label(npc_key), "turns": chat.turns, "duration_s": int(now - chat.start)}
        if abandoned:
            props["abandoned"] = True
        self.record(Event.CHAT_END, session, **props)


recorder = AnalyticsRecorder()


# -- request-bound conveniences ---------------------------------------------


def bind_request_session(session):
    """Attach ``session`` to this request for ``record``, and beat on player activity."""
    if not recorder.enabled or session is None or not has_request_context():
        return
    g.analytics_session = session
    if request.method in ACTIVITY_METHODS:
        recorder.heartbeat(session)


def request_session():
    """The session bound to the current request, or None."""
    return g.get("analytics_session") if has_request_context() else None


def record(event, **props):
    """Record ``event`` for the session bound to the current request."""
    recorder.record(event, request_session(), **props)


def rebaseline(session, player, game_service=None):
    """Take a fresh progress baseline for ``session`` from ``player``.

    Called where the player object is replaced wholesale (sign-in, new game,
    load), so that the next request's diff is against the new game rather
    than the old one. ``game_service`` defaults to the app's.
    """
    if not recorder.enabled or session is None or player is None:
        return
    with _swallowed("rebaseline"):
        service = game_service or current_app.game_service
        recorder.reset_progress(session, service.analytics_markers(player))


def _session_player(session_manager, session):
    """The player behind ``session``, read from ``session_manager.players``.

    Not ``get_player``: that re-runs session lookup, reaping and the access
    bump, which an after-request hook must not do, and logout may already
    have removed the session.
    """
    return session_manager.players.get(session.player_id)


def on_sign_in(session, session_manager, event):
    """Record a sign-in (``Event.LOGIN``/``Event.REGISTER``) for a new session.

    Takes the session explicitly: it was created during this request, after
    the middleware had nothing to bind. The player is looked up only when
    recording is on.
    """
    if not recorder.enabled:
        return
    recorder.record(event, session)
    recorder.heartbeat(session)
    rebaseline(session, _session_player(session_manager, session))


def observe_request_progress(session_manager, game_service):
    """Diff the bound session's progress markers against the last request's.

    Registered after every request by ``_init_analytics``, which covers every
    path that can move the player or set a story flag without instrumenting
    each of them.
    """
    if not recorder.enabled:
        return
    session = request_session()
    if session is None:
        return
    with _swallowed("progress observation"):
        player = _session_player(session_manager, session)
        if player is not None:
            recorder.observe_progress(session, game_service.analytics_markers(player))
