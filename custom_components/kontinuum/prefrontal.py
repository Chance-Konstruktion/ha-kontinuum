"""Minimal decision gate for the First Autonomous Action Loop (FAL)."""


class PrefrontalCortex:
    """Decides whether an autonomous action should be executed."""

    def decide(self, confidence: float, q_value: float) -> bool:
        if confidence >= 0.7 and q_value > 0:
            return True
        return False
