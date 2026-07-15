"""Defensive serialization boundary (issue #295).

Enforces the two serializer-contract invariants from CLAUDE.md for *every*
serializer, against degraded / partial / ``_legacy_placeholder`` engine objects
whose attributes may be missing, ``None``, or the wrong type:

  * **A serializer never raises.** On any internal error it returns a best-effort
    empty result (``[]`` for a ``*_list`` method, else ``{}``) instead of letting
    an ``AttributeError``/``TypeError``/``ValueError`` escape into a route
    handler and 500 the whole request. This matches the project convention of
    preferring silent recovery over crashing the game loop.
  * **Its output is always JSON-serializable.** ``set``/``tuple`` become lists,
    non-finite floats (NaN/inf) become ``None``, non-string dict keys are
    stringified, and any stray non-primitive (a leaked engine object) becomes
    its ``str`` — so ``jsonify`` can never choke on the result.

Applied once per serializer class via :func:`harden_serializer` in the package
``__init__`` (which runs on every serializer import path), keeping the
individual serializers free of repetitive per-field getattr/try guards.
"""

import functools
import math

_MAX_DEPTH = 40


def json_safe(value, _depth=0):
    """Return a JSON-serializable deep copy of `value`.

    Primitives pass through; non-finite floats become ``None``; sets/tuples
    become lists; dict keys are coerced to ``str``; anything else becomes its
    ``str``. Depth-capped so a cyclic/self-referential degraded graph cannot
    recurse without bound.
    """
    if _depth > _MAX_DEPTH:
        return None
    if value is None or isinstance(value, bool) or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            key = k if isinstance(k, str) else str(k)
            out[key] = json_safe(v, _depth + 1)
        return out
    if isinstance(value, (list, tuple, set, frozenset)):
        return [json_safe(v, _depth + 1) for v in value]
    return str(value)


def _wrap(name, fn):
    fallback_list = name.endswith("_list")

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return json_safe(fn(*args, **kwargs))
        except Exception:  # noqa: BLE001 - contract: a serializer never raises
            return [] if fallback_list else {}

    return wrapper


def harden_serializer(cls):
    """Wrap each JSON-producing method of a serializer class with the boundary.

    Only methods whose name starts with ``serialize`` are wrapped: those are the
    public entry points that build JSON dicts/lists and must never raise. Numeric
    helper methods (``get_effective_buy_modifier``, ``get_price_modifier``, …)
    return scalars used in downstream arithmetic, so they are deliberately left
    untouched — wrapping them would coerce a failure into ``{}`` and break price
    math.
    """
    for name, member in list(vars(cls).items()):
        if not name.startswith("serialize"):
            continue
        if isinstance(member, staticmethod):
            setattr(cls, name, staticmethod(_wrap(name, member.__func__)))
        elif isinstance(member, classmethod):
            setattr(cls, name, classmethod(_wrap(name, member.__func__)))
        elif callable(member):
            setattr(cls, name, _wrap(name, member))
    return cls
