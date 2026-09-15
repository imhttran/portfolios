"""The free / paid / premium vocabulary, shared by albums and subscriptions.

One ladder, read two ways:

- an **album's tier** says what it takes to download it;
- a **subscription's level** says how far up it reaches.

A subscription at level L opens every album whose tier ranks at or below L, so
`premium` opens premium and paid albums, and `paid` opens only paid ones.

The names are deliberately the same on both sides: a subscription's level names
the highest album tier it unlocks.
"""

from __future__ import annotations

TIER_FREE = "free"
TIER_PAID = "paid"
TIER_PREMIUM = "premium"

TIERS: tuple[str, ...] = (TIER_FREE, TIER_PAID, TIER_PREMIUM)

# What a subscription can be set to. Free isn't an option: access at that tier
# needs no subscription at all.
SUBSCRIPTION_LEVELS: tuple[str, ...] = (TIER_PAID, TIER_PREMIUM)


def tier_rank(tier: str) -> int | None:
    """Position on the ladder, or None if the value isn't one we know."""
    try:
        return TIERS.index(tier)
    except ValueError:
        return None


def opens(tier: str, level: str) -> bool:
    """Does a subscription at ``level`` open an album at ``tier``?

    Unrecognised values on either side return False: an unknown tier or level
    must never be more permissive than the one someone meant to type.
    """
    tier_position = tier_rank(tier)
    level_position = tier_rank(level)
    if tier_position is None or level_position is None:
        return False
    return tier_position <= level_position
