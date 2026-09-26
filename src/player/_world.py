"""World-admin mixin for Player — merchant refresh and shop management."""

import time

from src.narration import cprint
from src.shop_conditions import iter_merchants


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

        merchants = []
        for npc in iter_merchants(getattr(self.universe, "maps", [])):
            try:
                npc_name = (getattr(npc, "name", "") or "").lower()
            except Exception:
                # Skip any problematic object
                continue
            if target_filter and target_filter not in npc_name:
                continue
            merchants.append(npc)

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

        success = 0
        failures = []  # list[tuple[str, str]]
        for m in merchants:
            try:
                # If vendor needs shop initialization
                if getattr(m, "shop", None) is None and hasattr(m, "initialize_shop"):
                    try:
                        m.initialize_shop()
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
