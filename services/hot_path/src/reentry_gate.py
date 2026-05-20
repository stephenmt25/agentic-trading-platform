"""Re-entry gate — one open position per (profile, symbol).

The hot-path processor emits an order on *every* tick the entry condition
holds. Without this gate a single sustained signal pyramids dozens of
positions into the same symbol — the live failure mode observed on the
Phase 0 soak: 192 ETH/USDT positions opened in a 17-second burst while RSI
sat below the entry threshold.

The backtester already models one-position-at-a-time
(`services/backtesting/src/simulator.py` only opens `if not open_trade`);
this gate brings the live engine into line.

`ProfileState.open_position_symbols` is the source of truth: reconciled from
the positions table by `PnlSync` every 5 s, and optimistically updated by the
processor the instant an order is emitted — so the gate is correct within the
poll window even before the position row is visible.
"""

from .state import ProfileState


class ReentryGate:
    @staticmethod
    def check(profile_state: ProfileState, symbol: str) -> bool:
        """Return True if a re-entry should be BLOCKED — i.e. the profile
        already holds an open position on this symbol."""
        return symbol in profile_state.open_position_symbols
