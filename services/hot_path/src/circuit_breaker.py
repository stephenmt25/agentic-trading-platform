from .state import ProfileState
import datetime

class CircuitBreaker:
    @staticmethod
    def check(state: ProfileState) -> bool:
        # Check if daily realised P&L exceeds circuit_breaker_daily_loss_pct
        # True = tripped
        
        # NOTE: Resetting logic at midnight UTC would be handled by 
        # a scheduled cron job resetting state.daily_realised_pnl_pct.
        
        # If daily pnl is a negative float representing percentage
        loss_pct = -state.daily_realised_pnl_pct
        
        if loss_pct > float(state.risk_limits.circuit_breaker_daily_loss_pct):
            return True
        return False
