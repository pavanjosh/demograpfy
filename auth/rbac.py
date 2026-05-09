import os
from dotenv import load_dotenv

load_dotenv()

FREE_TIER_LIMIT = int(os.getenv("FREE_TIER_LIMIT", 5))
BASIC_TIER_LIMIT = int(os.getenv("BASIC_TIER_LIMIT", 20))
PR_TIER_LIMIT = int(os.getenv("PR_TIER_LIMIT", 50))  # 50


def get_usage_limit(tier: str) -> int | None:
    """
    Returns the question limit for a given tier.
    Returns None for unlimited tiers.
    """
    tier = (tier or "free").lower()
    if tier == "free":
        return FREE_TIER_LIMIT
    elif tier == "basic":
        return BASIC_TIER_LIMIT
    elif tier == "pro":
        return None if PR_TIER_LIMIT == -1 else PR_TIER_LIMIT
    return FREE_TIER_LIMIT  # default to free for unknown tiers


def is_within_limit(usage: int, tier: str) -> bool:
    """Returns True if the user has not exceeded their tier's question limit."""
    limit = get_usage_limit(tier)
    return True if limit is None else usage < limit


def is_near_limit(usage: int, tier: str) -> bool:
    """Returns True if usage has reached 80% or more of the tier limit."""
    limit = get_usage_limit(tier)
    if limit is None:
        return False
    return usage >= limit * 0.8
