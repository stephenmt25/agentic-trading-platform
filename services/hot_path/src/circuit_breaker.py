from .state import ProfileState
import datetime

class CircuitBreaker:
    # Track the last date we checked per profile to detect day rollover
    _last_reset_date: dict = {}

    @classmethod
    def check(cls, state: ProfileState) -> bool:
        """Check if daily realised P&L exceeds circuit_breaker_daily_loss_pct.

        Returns True if circuit breaker is tripped.
        Automatically resets daily PnL at midnight UTC.
        """
        today_utc = datetime.datetime.now(datetime.timezone.utc).date()
        last_date = cls._last_reset_date.get(state.profile_id)

        if last_date is not None and last_date < today_utc:
            # New trading day: reset daily PnL
            state.daily_realised_pnl_pct = 0.0

        cls._last_reset_date[state.profile_id] = today_utc

        loss_pct = -state.daily_realised_pnl_pct

        if loss_pct > float(state.risk_limits.circuit_breaker_daily_loss_pct):
            return True
        return False
