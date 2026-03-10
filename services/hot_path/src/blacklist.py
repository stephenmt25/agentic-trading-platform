from .state import ProfileState

class BlacklistChecker:
    @staticmethod
    def check(state: ProfileState, symbol: str) -> bool:
        """O(1) set membership check."""
        return symbol in state.blacklist
