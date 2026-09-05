"""``wsgi.py`` serves ProductionConfig or nothing at all.

This is the entry point gunicorn binds to a public listener, and until the
guard under test existed it would happily serve ``DevelopmentConfig`` there.
Three separate spellings reached that outcome, two of them in silence:

* ``FLASK_ENV`` unset -- :func:`~src.api.config.normalized_env` defaults to
  ``"development"``, and nothing is logged.
* ``FLASK_ENV`` exported but blank -- ``config_for_env``'s falsy branch, which
  warns about nothing.
* ``FLASK_ENV=prod`` -- warns, and still returns ``DevelopmentConfig``.

What each of them bought is enumerated in ``config_for_env``'s own docstring:
``DEBUG=True``, ``SESSION_COOKIE_SECURE=False``, localhost-only CORS origins,
and a fresh ``os.urandom(24)`` SECRET_KEY per worker -- so sessions neither
survive a worker recycle nor work across workers.

The asymmetry is deliberate and is asserted below: ``config_for_env`` still
defaults to development, because that is the right answer on a developer's
box. ``wsgi.py`` is not a developer's box, so it requires the word.
"""

import importlib.util
import pathlib

import pytest

import src.api.app as api_app
import src.env_bootstrap as env_bootstrap
from src.api.config import DevelopmentConfig, config_for_env

_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture
def boot(monkeypatch):
    """Execute ``wsgi.py`` with a controlled environment and a stub factory.

    ``load_project_env`` is neutralised because it reads the developer's real
    ``.env``, which carries its own ``FLASK_ENV`` -- without this the "unset"
    case below would silently test whatever that file happens to say.
    ``create_app`` is stubbed so a refusal that fires *after* the app is built
    cannot pass: the sentinel is the proof the factory ran at all.
    """
    sentinel = (object(), object())
    built = []

    def _stub_create_app(*args, **kwargs):
        built.append(args)
        return sentinel

    monkeypatch.setattr(env_bootstrap, "load_project_env", lambda *a, **k: None)
    monkeypatch.setattr(api_app, "create_app", _stub_create_app)

    def _boot(flask_env):
        if flask_env is None:
            monkeypatch.delenv("FLASK_ENV", raising=False)
        else:
            monkeypatch.setenv("FLASK_ENV", flask_env)
        spec = importlib.util.spec_from_file_location(
            "hov_wsgi_production_guard", _ROOT / "wsgi.py"
        )
        module = importlib.util.module_from_spec(spec)
        # Deliberately not registered in sys.modules: a throwaway execution of
        # the entry point, not an import of it.
        spec.loader.exec_module(module)
        return module

    _boot.sentinel = sentinel
    _boot.built = built
    return _boot


@pytest.mark.parametrize(
    "flask_env",
    [
        None,  # unset -> normalized_env() defaults to "development"
        "",  # exported but blank -> config_for_env's silent falsy branch
        "prod",  # the typo that warns and serves development anyway
        "development",
    ],
)
def test_only_the_word_production_boots(boot, flask_env):
    with pytest.raises(SystemExit) as excinfo:
        boot(flask_env)
    message = str(excinfo.value)
    # The message has to name the variable and the value, or the operator
    # cannot tell this refusal from the TESTING one two lines above it.
    assert "FLASK_ENV" in message
    expected = "development" if flask_env is None else flask_env.strip().lower()
    assert repr(expected) in message
    # ...and it has to say what it would have cost, or it reads as pedantry
    # and gets deleted.
    assert "SECRET_KEY" in message
    assert "SESSION_COOKIE_SECURE" in message


def test_the_refusal_fires_before_the_app_is_ever_built(boot):
    """Refusing after ``create_app`` would already have loaded the universe
    and registered every blueprint; the point is not to build it."""
    with pytest.raises(SystemExit):
        boot("development")
    assert boot.built == []


@pytest.mark.parametrize("flask_env", ["production", "Production", "  PRODUCTION  "])
def test_production_still_boots(boot, flask_env):
    """The negative control, on every spelling ``normalized_env`` accepts.

    A refusal that fired for everything would pass every assertion above while
    breaking the only launch that matters -- and one that compared the raw
    variable instead of the normalised one would reject ``Production`` while
    ``config_for_env`` accepted it, which is the exact split
    :func:`~src.api.config.normalized_env` exists to prevent.
    """
    module = boot(flask_env)
    assert (module.app, module.socketio) == boot.sentinel


@pytest.mark.parametrize("flask_env", ["", "prod", "development"])
def test_the_shared_mapping_still_defaults_to_development(flask_env):
    """The asymmetry is the fix, so it is asserted rather than assumed.

    ``config_for_env`` is shared with ``tools/run_api.py``, which serves a dev
    server on 127.0.0.1; hardening the *mapping* would take developer defaults
    away to fix a production entry point. The guard belongs in ``wsgi.py``
    alone, and this fails if someone later "tidies" it into the mapping.
    """
    assert config_for_env(flask_env) is DevelopmentConfig
