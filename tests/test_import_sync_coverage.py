"""Coverage for src/import_sync.py — the bare<->src.* import aliasing hook
used by production entry points (wsgi.py, tools/run_api.py).

install()/_sync_all_src() iterate and mutate the ENTIRE `sys.modules` dict
and install()/monkeypatches `builtins.__import__` process-wide. Per the
docstring on tests/test_import_sync_production.py, exercising this for real
in-process is unsafe: tests/conftest.py installs its own competing bare<->src
sync hook for the whole session, and any leftover mutation to the live
`sys.modules`/`builtins.__import__` would corrupt every later test in the
run. So every test here runs against an isolated *copy* of `sys.modules`
(swapped in via monkeypatch, which guarantees restoration even on failure)
rather than the live one — real module objects are still visible for reads,
but no write here can ever escape into the shared process state.
"""

import builtins
import pathlib
import sys
import types

import pytest

import src.import_sync as import_sync


@pytest.fixture
def isolated_import_state(monkeypatch):
    """Give the test its own throwaway sys.modules copy + import hook state."""
    monkeypatch.setattr(sys, "modules", dict(sys.modules))
    monkeypatch.setattr(builtins, "__import__", sys.modules["conftest"]._original_import)
    monkeypatch.setattr(import_sync, "_installed", False)


def test_sync_all_src_aliases_bare_name_to_src_module(isolated_import_state):
    fake = types.ModuleType("src.fake_sync_target")
    sys.modules["src.fake_sync_target"] = fake
    sys.modules.pop("fake_sync_target", None)

    import_sync._sync_all_src()
    assert sys.modules["fake_sync_target"] is fake


def test_sync_all_src_skips_none_and_excluded_names(isolated_import_state):
    sys.modules["src.api"] = types.ModuleType("src.api")
    sys.modules["src.none_module"] = None

    # Should not raise, and must not alias the excluded "api" bare name.
    import_sync._sync_all_src()
    assert "api" not in sys.modules or sys.modules["api"] is not sys.modules["src.api"]


def test_sync_all_src_does_not_overwrite_existing_matching_alias(isolated_import_state):
    fake = types.ModuleType("src.fake_sync_target2")
    sys.modules["src.fake_sync_target2"] = fake
    sys.modules["fake_sync_target2"] = fake

    # already aliased -> the `is not` check short-circuits (no-op branch)
    import_sync._sync_all_src()
    assert sys.modules["fake_sync_target2"] is fake


def test_install_is_idempotent(isolated_import_state):
    import_sync._installed = True
    hook_before = builtins.__import__
    import_sync.install()
    assert builtins.__import__ is hook_before  # no-op: returned early


def test_install_patches_import_and_syncs_bare_alias(isolated_import_state):
    fake = types.ModuleType("src.fake_install_target")
    sys.modules["src.fake_install_target"] = fake
    sys.modules.pop("fake_install_target", None)

    import_sync.install()
    assert builtins.__import__ is not None
    # Triggers the `name.startswith("src.")` branch in _synchronized_import
    __import__("src.fake_install_target")
    assert sys.modules["fake_install_target"] is fake


def test_installed_hook_redirects_fresh_bare_import_to_canonical_src(isolated_import_state):
    """Covers the elif branch: a bare module loaded while src.* already
    exists gets redirected to the canonical src.* object."""
    import_sync.install()

    canonical = types.ModuleType("src.fake_redirect_target")
    sys.modules["src.fake_redirect_target"] = canonical
    sys.modules.pop("fake_redirect_target", None)

    stale = types.ModuleType("fake_redirect_target")
    sys.modules["fake_redirect_target"] = stale
    __import__("fake_redirect_target")
    assert sys.modules["fake_redirect_target"] is canonical


def test_installed_hook_skips_excluded_bare_name(isolated_import_state):
    """`api` is in _NO_BARE_ALIAS, so the elif branch must not touch it even
    if a matching src.api module exists."""
    import_sync.install()

    sys.modules.setdefault("src.api", types.ModuleType("src.api"))
    stale_api = types.ModuleType("api")
    sys.modules["api"] = stale_api
    __import__("api")
    # Must remain untouched by the hook (excluded name).
    assert sys.modules["api"] is stale_api


def test_install_core_order_reuses_existing_src_module(isolated_import_state, monkeypatch):
    """Covers the `mod in sys.modules and f"src.{mod}" in sys.modules` branch
    of the _CORE_ORDER loop: both bare and src.* already loaded -> reuse."""
    monkeypatch.setattr(import_sync, "_CORE_ORDER", ("fake_core_mod",))

    bare = types.ModuleType("fake_core_mod")
    src_ver = types.ModuleType("src.fake_core_mod")
    sys.modules["fake_core_mod"] = bare
    sys.modules["src.fake_core_mod"] = src_ver

    import_sync.install()
    # src.* is forced to be the bare object per the loop body.
    assert sys.modules["src.fake_core_mod"] is bare


def test_install_core_order_skips_when_only_one_side_present(isolated_import_state, monkeypatch):
    """Covers the `mod in sys.modules or f"src.{mod}" in sys.modules` continue
    branch: only one side present -> skip without importing."""
    monkeypatch.setattr(import_sync, "_CORE_ORDER", ("fake_partial_mod",))

    sys.modules.pop("fake_partial_mod", None)
    sys.modules.pop("src.fake_partial_mod", None)
    only_bare = types.ModuleType("fake_partial_mod")
    sys.modules["fake_partial_mod"] = only_bare

    import_sync.install()
    # No src.* counterpart should have been created for this module.
    assert "src.fake_partial_mod" not in sys.modules


def test_install_core_order_imports_missing_module_fresh(isolated_import_state, monkeypatch, tmp_path):
    """Covers the try-block success path: neither `mod` nor `src.mod` are
    loaded yet, so install() imports src.<mod> fresh and aliases both names
    to it. Uses a disposable throwaway module file (rather than a real src/
    module) so re-importing it can't create a second, diverging copy of a
    class other already-loaded tests rely on by identity.
    """
    throwaway = "_test_import_sync_throwaway_mod"
    module_file = pathlib.Path(__file__).resolve().parent.parent / "src" / f"{throwaway}.py"
    module_file.write_text("MARKER = 'loaded-fresh'\n")
    sys.modules.pop(throwaway, None)
    sys.modules.pop(f"src.{throwaway}", None)
    monkeypatch.setattr(import_sync, "_CORE_ORDER", (throwaway,))
    try:
        import_sync.install()
        assert throwaway in sys.modules
        assert sys.modules[throwaway] is sys.modules[f"src.{throwaway}"]
        assert sys.modules[throwaway].MARKER == "loaded-fresh"
    finally:
        # The module *file* is real (not covered by the sys.modules copy),
        # so it must always be cleaned up regardless of test outcome.
        module_file.unlink(missing_ok=True)


def test_install_core_order_handles_import_failure_gracefully(isolated_import_state, monkeypatch):
    """Covers the `except Exception: pass` branch: a core module that fails
    to import as src.* must not crash install()."""
    monkeypatch.setattr(import_sync, "_CORE_ORDER", ("definitely_not_a_real_module_xyz",))
    sys.modules.pop("definitely_not_a_real_module_xyz", None)
    sys.modules.pop("src.definitely_not_a_real_module_xyz", None)

    # Should not raise even though src.definitely_not_a_real_module_xyz
    # cannot be imported.
    import_sync.install()
    assert import_sync._installed is True


def test_state_fully_restored_after_each_test():
    """Sanity check: the isolated_import_state fixture must leave zero trace
    on the real process-wide sys.modules / builtins.__import__ / _installed.
    """
    assert import_sync._installed is False
    assert builtins.__import__ is sys.modules["conftest"]._synchronized_import
    assert "fake_sync_target" not in sys.modules
    assert "src.fake_install_target" not in sys.modules
