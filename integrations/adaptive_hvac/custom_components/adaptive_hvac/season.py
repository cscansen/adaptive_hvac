"""Season derivation from 7-day forecast with hysteresis."""

from dataclasses import dataclass, field

from .const import SEASON_SUMMER, SEASON_SHOULDER, SEASON_WINTER


@dataclass
class SeasonState:
    """Track season derivation with hysteresis."""
    current_season: str = SEASON_SHOULDER
    candidate_season: str = SEASON_SHOULDER
    consecutive_polls_in_candidate: int = 0
    hysteresis_threshold: int = 3


def derive_season(
    forecast_high_7day: float,
    forecast_low_7day: float,
    summer_threshold: float,
    winter_threshold: float,
    state: SeasonState,
) -> tuple[str, SeasonState]:
    """
    Derive season from 7-day forecast averages with hysteresis.

    Uses a 3-poll confirmation before transitioning to prevent flaky season changes.

    Args:
        forecast_high_7day: 7-day average high (°F)
        forecast_low_7day: 7-day average low (°F)
        summer_threshold: High temp that triggers summer (default 75°F)
        winter_threshold: Low temp that triggers winter (default 40°F)
        state: Current season state tracker

    Returns:
        tuple of (derived_season, updated_state)
    """
    # Determine candidate season based on current forecast
    if forecast_high_7day > summer_threshold:
        candidate = SEASON_SUMMER
    elif forecast_low_7day < winter_threshold:
        candidate = SEASON_WINTER
    else:
        candidate = SEASON_SHOULDER

    # Update hysteresis counter
    if candidate == state.candidate_season:
        state.consecutive_polls_in_candidate += 1
    else:
        # Candidate changed, reset counter
        state.candidate_season = candidate
        state.consecutive_polls_in_candidate = 1

    # Commit to new season if hysteresis threshold met
    if state.consecutive_polls_in_candidate >= state.hysteresis_threshold:
        state.current_season = candidate
        state.consecutive_polls_in_candidate = 0

    return state.current_season, state
