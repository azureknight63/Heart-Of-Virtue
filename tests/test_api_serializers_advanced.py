"""
Tests for advanced API serializers:
- api/serializers/reputation.py (NPCRelationshipSerializer)

Every band in this module is a *boundary* rule (``>= 50``, ``>= 25``, ...),
so the tests parametrize over the boundary values themselves rather than one
comfortable value per band: an off-by-one that moved "friendly" from 50 to 51
was invisible to a test that only ever asked about 75.
"""

import pytest

from src.api.serializers.reputation import NPCRelationshipSerializer as Rep

# ===========================================================================
# NPCRelationshipSerializer
# ===========================================================================


class TestSerializeRelationship:
    # (reputation, attitude, emoji, trust_level) at and around every boundary.
    BANDS = [
        (100, "friendly", "\U0001F60A", "Complete Trust"),
        (75, "friendly", "\U0001F60A", "Complete Trust"),
        (74, "friendly", "\U0001F60A", "High Trust"),
        (50, "friendly", "\U0001F60A", "High Trust"),
        (49, "favorable", "\U0001F642", "Good Trust"),
        (25, "favorable", "\U0001F642", "Good Trust"),
        (24, "neutral", "\U0001F610", "Neutral"),
        (0, "neutral", "\U0001F610", "Neutral"),
        (-1, "wary", "\U0001F615", "Suspicious"),
        (-25, "wary", "\U0001F615", "Suspicious"),
        (-26, "hostile", "\U0001F620", "Distrusting"),
        (-50, "hostile", "\U0001F620", "Distrusting"),
        (-51, "enemy", "\U0001F621", "Hostile"),
        (-100, "enemy", "\U0001F621", "Hostile"),
    ]

    @pytest.mark.parametrize("reputation, attitude, emoji, trust", BANDS)
    def test_full_payload_at_every_band_boundary(
        self, reputation, attitude, emoji, trust
    ):
        """Asserts the whole dict, not just ``attitude``.

        ``emoji`` and ``trust_level`` are rendered by the npc-chat
        relationship badge; the previous tests read only ``attitude``, so the
        two bands whose attitude and trust boundaries differ (reputation 74
        and 49, where the attitude band and the trust band disagree) were
        never distinguished from their neighbours at all.
        """
        result = Rep.serialize_relationship("Gorran", "Gorran", reputation)
        assert result == {
            "npc_id": "Gorran",
            "npc_name": "Gorran",
            "reputation": reputation,
            "attitude": attitude,
            "emoji": emoji,
            "trust_level": trust,
        }

    def test_attitude_and_trust_bands_are_not_the_same_partition(self):
        """The reason the payload is asserted whole above.

        `attitude` splits at 50/25/0/-25/-50; `trust_level` splits at
        75/50/25/0/-25/-50. Two scores can share an attitude and differ in
        trust, so testing one is not testing the other.
        """
        high = Rep.serialize_relationship("g", "Gorran", 75)
        lower = Rep.serialize_relationship("g", "Gorran", 50)
        assert high["attitude"] == lower["attitude"] == "friendly"
        assert high["trust_level"] != lower["trust_level"]

    def test_npc_id_and_name_are_passed_through_independently(self):
        """They are distinct wire fields; a serializer that echoed one into
        both would look correct for every NPC whose id equals its name --
        which, per _get_npc_name's docstring, is currently all of them."""
        result = Rep.serialize_relationship("id-1", "Votha Krr", 10)
        assert result["npc_id"] == "id-1"
        assert result["npc_name"] == "Votha Krr"

    @pytest.mark.parametrize("reputation", [0, 25, 50, 75, -25, -50])
    def test_boundaries_are_inclusive_on_the_upper_side(self, reputation):
        """Each band uses ``>=``: the boundary value belongs to the *better*
        band, and one less belongs to the worse one."""
        at = Rep._calculate_trust_level(reputation)
        below = Rep._calculate_trust_level(reputation - 1)
        assert at != below


class TestCalculateTrustLevel:
    @pytest.mark.parametrize(
        "reputation, expected",
        [
            (80, "Complete Trust"),
            (60, "High Trust"),
            (30, "Good Trust"),
            (10, "Neutral"),
            (-10, "Suspicious"),
            (-40, "Distrusting"),
            (-80, "Hostile"),
        ],
    )
    def test_trust_levels(self, reputation, expected):
        assert Rep._calculate_trust_level(reputation) == expected


class TestGetNpcName:
    def test_get_npc_name_returns_input_unchanged(self):
        """_get_npc_name is a passthrough: reputation is keyed by NPC display
        name already."""
        assert Rep._get_npc_name("Gorran") == "Gorran"
        assert Rep._get_npc_name("Votha Krr") == "Votha Krr"


class TestGetPriceModifier:
    """Shop pricing reads this (``shop_serializer._effective_modifiers``), and
    it was untested in the default suite -- the only coverage lived in
    ``tests/api/``, which pytest.ini excludes from the standard run."""

    @pytest.mark.parametrize(
        "reputation, expected",
        [
            (100, 0.15),
            (50, 0.075),
            (0, 0.0),
            (-50, -0.075),
            (-100, -0.15),
        ],
    )
    def test_scales_linearly_to_the_declared_swing(self, reputation, expected):
        assert Rep.get_price_modifier(reputation) == pytest.approx(expected)

    def test_sign_convention_favours_the_player_when_positive(self):
        """The docstring's contract: apply as ``buy * (1 - modifier)`` and
        ``sell * (1 + modifier)``. A flipped sign would make friendly
        merchants *more* expensive -- arithmetic that still "works", so only
        the sign pins it."""
        friendly = Rep.get_price_modifier(80)
        hostile = Rep.get_price_modifier(-80)
        assert friendly > 0 > hostile
        assert friendly == pytest.approx(-hostile)
        # A friendly merchant's buy price really is lower.
        assert 100 * (1 - friendly) < 100 < 100 * (1 - hostile)

    def test_swing_is_bounded_by_the_named_constant(self):
        assert Rep.REPUTATION_PRICE_SWING == 0.15
        for reputation in range(-100, 101, 5):
            assert abs(Rep.get_price_modifier(reputation)) <= Rep.REPUTATION_PRICE_SWING
