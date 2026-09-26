"""World-admin mixin for Player — merchant refresh and shop management."""

import time

from src.narration import cprint
from src.shop_conditions import iter_merchants


def _readable_name(npc):
    """``npc``'s name, lower-cased, or None when reading it raises."""
    try:
        return str(getattr(npc, "name", "") or "").lower()
    except Exception:
        return None


class PlayerWorldMixin:
    """World and merchant administration commands for the Player."""

    def refresh_merchants(self, phrase: str = ""):
        """Debug command: iterate all maps and force every Merchant to run update_goods().

        Optional phrase filters merchants by case-insensitive substring in their name.
        Provides a concise summary of successes and any failures.
        """
        # Defensive: guard if universe/maps not present
        if not self.universe or not hasattr(self.universe, "maps"):
            cprint("Universe not initialized; cannot refresh merchants.", "red")
            return

        target_filter = phrase.lower().strip() if phrase else ""

        # An empty filter matches every name; a merchant whose name cannot be
        # read is skipped rather than allowed to abort the sweep.
        named = ((m, _readable_name(m)) for m in iter_merchants(self.universe.maps))
        merchants = [m for m, name in named if name is not None and target_filter in name]

        if not merchants:
            cprint(
                (
                    "No merchants found to refresh."
                    if not target_filter
                    else f"No merchants matched filter '{target_filter}'."
                ),
                "yellow",
            )
            return

        # Local: src.npc imports src.objects, which imports src.player.
        from src.npc._shop import MerchantShopMixin

        success = 0
        failures = []  # list[tuple[str, str]]
        for m in merchants:
            try:
                try:
                    # Unbound, so duck-typed merchants get the same check.
                    MerchantShopMixin.ensure_shop_initialized(m)
                except Exception:
                    # non-fatal; continue to try update_goods
                    pass
                update_fn = getattr(m, "update_goods", None)
                if callable(update_fn):
                    try:
                        update_fn()
                        success += 1
                    except Exception as e:
                        failures.append((getattr(m, "name", "<unknown>"), str(e)))
                else:
                    failures.append(
                        (
                            getattr(m, "name", "<unknown>"),
                            "missing update_goods",
                        )
                    )
            except Exception as e:
                failures.append((getattr(m, "name", "<unknown>"), str(e)))

        cprint(
            f"Merchant refresh complete: {success} succeeded, {len(failures)} failed.",
            "cyan",
        )
        if failures:
            for name, err in failures[:10]:
                cprint(f" - {name}: {err}", "red")
        # Small pause for readability in interactive sessions
        time.sleep(0.1)
