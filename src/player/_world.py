"""World-admin mixin for Player — merchant refresh and shop management."""

import time

from neotermcolor import cprint


class PlayerWorldMixin:
    """World and merchant administration commands for the Player."""

    def refresh_merchants(self, phrase: str = ''):
        """Debug command: iterate all maps and force every Merchant to run update_goods().

        Optional phrase filters merchants by case-insensitive substring in their name.
        Provides a concise summary of successes and any failures.
        """
        # Defensive: guard if universe/maps not present
        if not self.universe or not hasattr(self.universe, 'maps'):
            cprint("Universe not initialized; cannot refresh merchants.", 'red')
            return

        target_filter = phrase.lower().strip() if phrase else ''

        # Helper: returns True for objects whose class MRO contains a class named 'Merchant'.
        def _is_merchant_instance(obj):
            if obj is None:
                return False
            cls = getattr(obj, '__class__', None)
            if cls is None:
                return False
            try:
                mro = getattr(cls, 'mro', None)
                if not callable(mro):
                    return False
                return any(getattr(c, '__name__', '') == 'Merchant' for c in cls.mro())
            except Exception:
                return False

        merchants = []
        for game_map in getattr(self.universe, 'maps', []):  # each map is a dict
            if not isinstance(game_map, dict):
                continue
            for coord, tile in game_map.items():
                if coord == 'name':
                    continue
                if not tile:
                    continue
                for npc in getattr(tile, 'npcs_here', []):
                    try:
                        if _is_merchant_instance(npc):
                            npc_name = (getattr(npc, 'name', '') or '').lower()
                            if target_filter and target_filter not in npc_name:
                                continue
                            merchants.append(npc)
                    except Exception:
                        # Skip any problematic object
                        continue

        if not merchants:
            cprint("No merchants found to refresh." if not target_filter else
                   f"No merchants matched filter '{target_filter}'.", 'yellow')
            return

        success = 0
        failures = []  # list[tuple[str, str]]
        for m in merchants:
            try:
                # If vendor needs shop initialization
                if getattr(m, 'shop', None) is None and hasattr(m, 'initialize_shop'):
                    try:
                        m.initialize_shop()
                    except Exception:
                        # non-fatal; continue to try update_goods
                        pass
                update_fn = getattr(m, 'update_goods', None)
                if callable(update_fn):
                    try:
                        update_fn()
                        success += 1
                    except Exception as e:
                        failures.append((getattr(m, 'name', '<unknown>'), str(e)))
                else:
                    failures.append((getattr(m, 'name', '<unknown>'), 'missing update_goods'))
            except Exception as e:
                failures.append((getattr(m, 'name', '<unknown>'), str(e)))

        cprint(f"Merchant refresh complete: {success} succeeded, {len(failures)} failed.", 'cyan')
        if failures:
            for name, err in failures[:10]:
                cprint(f" - {name}: {err}", 'red')
        # Small pause for readability in interactive sessions
        time.sleep(0.1)
