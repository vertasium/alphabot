"""
AlphaBot v4.0 — Regime Detection Engine
Detects market regime: Bull, Bear, High Vol, Low Vol, Range-Bound, Crash
Uses rule-based detection per PRD FR-DIR-001.
"""
import numpy as np
from typing import Dict
from core.models import RegimeResult, RegimeType
import logging

logger = logging.getLogger("alphabot.regime")


class RegimeDetector:
    """
    Market regime detection using rule-based logic (PRD Section 4.5).
    6 regimes: bull_trend, bear_trend, high_vol, low_vol, range_bound, crash
    """

    def __init__(self, config=None):
        from config import REGIME
        self.config = config or REGIME

    def detect(self, market_data: Dict) -> RegimeResult:
        """Detect current market regime"""
        vix = market_data.get('vix', 15.0)
        spy_price = market_data.get('spy_price', 0)
        spy_ema200 = market_data.get('spy_ema200', 0)
        adx = market_data.get('adx', 20)
        plus_di = market_data.get('plus_di', 0)
        minus_di = market_data.get('minus_di', 0)
        avg_correlation = market_data.get('avg_correlation', 0.3)
        sector_breadth = market_data.get('sector_breadth', 0.5)
        
        # Crash detection (highest priority)
        if vix > self.config.crash_vix_threshold and avg_correlation > self.config.crash_correlation_threshold:
            return RegimeResult(
                regime=RegimeType.CRASH,
                confidence=0.95,
                rule_regime="crash",
                features=market_data
            )
        
        # Bull trend
        if (spy_price > spy_ema200 and spy_ema200 > 0 and
            adx > self.config.bull_adx_min and 
            vix < self.config.bull_vix_max and
            plus_di > minus_di):
            confidence = min(0.9, 0.6 + (adx - 25) / 100 + (20 - vix) / 100)
            return RegimeResult(
                regime=RegimeType.BULL_TREND,
                confidence=max(0.6, confidence),
                rule_regime="bull_trend",
                features=market_data
            )
        
        # Bear trend
        if (spy_price < spy_ema200 and spy_ema200 > 0 and
            adx > self.config.bear_adx_min and 
            vix > self.config.bear_vix_min and
            minus_di > plus_di):
            confidence = min(0.9, 0.6 + (adx - 25) / 100 + (vix - 25) / 100)
            return RegimeResult(
                regime=RegimeType.BEAR_TREND,
                confidence=max(0.6, confidence),
                rule_regime="bear_trend",
                features=market_data
            )
        
        # High volatility
        if vix > self.config.high_vol_vix_min:
            return RegimeResult(
                regime=RegimeType.HIGH_VOL,
                confidence=min(0.85, 0.6 + (vix - 30) / 50),
                rule_regime="high_vol",
                features=market_data
            )
        
        # Low volatility
        if vix < self.config.low_vol_vix_max:
            return RegimeResult(
                regime=RegimeType.LOW_VOL,
                confidence=min(0.85, 0.6 + (15 - vix) / 30),
                rule_regime="low_vol",
                features=market_data
            )
        
        # Range-bound (default)
        return RegimeResult(
            regime=RegimeType.RANGE_BOUND,
            confidence=0.6,
            rule_regime="range_bound",
            features=market_data
        )

    def get_regime_allocation(self, regime: RegimeType) -> Dict[str, float]:
        """Get strategy cluster allocation weights for regime"""
        allocations = {
            RegimeType.BULL_TREND: {
                "momentum": 0.25, "long_short_equity": 0.20,
                "event_driven": 0.15, "options_advanced": 0.10,
                "global_macro": 0.10, "hedge": 0.20
            },
            RegimeType.BEAR_TREND: {
                "mean_reversion": 0.20, "volatility": 0.15,
                "long_short_equity": 0.15, "global_macro": 0.10,
                "options_advanced": 0.10, "cash": 0.30
            },
            RegimeType.HIGH_VOL: {
                "volatility": 0.35, "ml_ai": 0.20,
                "microstructure": 0.15, "stat_arb": 0.15,
                "cash": 0.15
            },
            RegimeType.LOW_VOL: {
                "mean_reversion": 0.35, "stat_arb": 0.25,
                "microstructure": 0.20, "ml_ai": 0.20
            },
            RegimeType.RANGE_BOUND: {
                "mean_reversion": 0.35, "stat_arb": 0.25,
                "microstructure": 0.20, "ml_ai": 0.20
            },
            RegimeType.CRASH: {
                "cash": 0.85, "volatility": 0.05,
                "global_macro": 0.05, "stat_arb": 0.05
            }
        }
        return allocations.get(regime, allocations[RegimeType.RANGE_BOUND])
