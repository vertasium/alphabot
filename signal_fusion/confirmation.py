"""
AlphaBot v4.0 — Signal Fusion & Confirmation Engine
Requires >= 3 confirming signals from different clusters (PRD FR-SELECT-001).
"""
import numpy as np
from typing import List, Dict
from core.models import Signal
import logging

logger = logging.getLogger("alphabot.fusion")

CLUSTER_WEIGHTS = {
    'momentum': 1.0, 'mean_reversion': 1.0, 'volatility': 0.8,
    'stat_arb': 1.2, 'microstructure': 0.9, 'ml_ai': 1.1,
    'long_short_equity': 1.0, 'event_driven': 1.0,
    'options_advanced': 0.8, 'global_macro': 1.0
}


def confirm_signals(signals: List[Signal], min_confirmations: int = 2, min_confidence: float = 0.60) -> List[Signal]:
    """Multi-strategy confirmation per PRD FR-SELECT-001"""
    if not signals:
        return []

    # Group by symbol
    by_symbol: Dict[str, List[Signal]] = {}
    for sig in signals:
        by_symbol.setdefault(sig.symbol, []).append(sig)

    confirmed = []
    for symbol, sigs in by_symbol.items():
        if len(sigs) < min_confirmations:
            continue

        # Check cluster diversity
        clusters = set(s.cluster for s in sigs if s.cluster)
        if len(clusters) < min(min_confirmations, 2):
            continue

        # Calculate weighted confidence
        total_w, weighted_sum = 0, 0
        for s in sigs:
            w = CLUSTER_WEIGHTS.get(s.cluster, 1.0)
            # Anti-correlation penalty
            same_cluster = sum(1 for x in sigs if x.cluster == s.cluster and x != s)
            penalty = min(same_cluster * 0.2, 0.5)
            adj_w = w * (1 - penalty)
            weighted_sum += s.confidence * adj_w
            total_w += adj_w

        avg_conf = weighted_sum / total_w if total_w > 0 else 0

        if avg_conf < min_confidence:
            continue

        # Consolidate into one signal
        weights = [s.confidence for s in sigs]
        entry = np.average([s.entry_price for s in sigs], weights=weights)
        
        # Majority direction
        long_count = sum(1 for s in sigs if s.direction.value == "LONG")
        short_count = sum(1 for s in sigs if s.direction.value == "SHORT")
        direction = sigs[0].direction
        if long_count > short_count:
            from core.models import Direction
            direction = Direction.LONG
        elif short_count > long_count:
            from core.models import Direction
            direction = Direction.SHORT

        best = max(sigs, key=lambda s: s.confidence)
        consolidated = Signal(
            symbol=symbol, direction=direction, confidence=avg_conf,
            entry_price=entry, stop_loss=best.stop_loss, take_profit=best.take_profit,
            position_size=min(sum(s.position_size for s in sigs), 0.05),
            strategy_id="CONSOLIDATED", cluster="multi",
            metadata={
                'strategies': [s.strategy_id for s in sigs],
                'clusters': list(clusters),
                'num_confirmations': len(sigs),
                'individual_confidences': [s.confidence for s in sigs]
            }
        )
        confirmed.append(consolidated)
        logger.info(f"✓ {symbol}: {len(sigs)} signals from {len(clusters)} clusters, conf={avg_conf:.2f}")

    return confirmed
