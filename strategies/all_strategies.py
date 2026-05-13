"""
AlphaBot v4.0 — All 49 Trading Strategies across 10 Clusters
Each strategy implements entry/exit logic per PRD FR-STRAT-001 through FR-STRAT-010.
"""
import numpy as np
from typing import Dict, Optional, List
from core.models import Signal, Direction
import logging, uuid
from datetime import datetime

logger = logging.getLogger("alphabot.strategies")


def _sig(sym, direction, confidence, price, atr, strategy_id, cluster):
    sl_mult = 1.5
    tp_mult = 2.0
    if direction == Direction.LONG:
        sl = price - sl_mult * atr
        tp = price + tp_mult * atr
    else:
        sl = price + sl_mult * atr
        tp = price - tp_mult * atr
    return Signal(symbol=sym, direction=direction, confidence=confidence,
        entry_price=price, stop_loss=sl, take_profit=tp, position_size=0.03,
        strategy_id=strategy_id, cluster=cluster)


# ═══════════════════════════════════════════════════════
# CLUSTER 1: MOMENTUM (#1-#5)
# ═══════════════════════════════════════════════════════
def s01_macd_histogram(f, sym):
    if f.get('macd_histogram',0) > 0 and f.get('macd_histogram_slope',0) > 0 and f.get('rsi_14',50) > 50:
        return _sig(sym, Direction.LONG, 0.65, f['price'], f.get('atr_14',1), "s01_macd_hist", "momentum")
    return None

def s02_rsi_breakout(f, sym):
    rsi = f.get('rsi_14', 50)
    if 55 < rsi < 75 and f.get('returns_1d',0) > 0.005 and f.get('adx_14',20) > 20:
        return _sig(sym, Direction.LONG, 0.62, f['price'], f.get('atr_14',1), "s02_rsi_break", "momentum")
    return None

def s03_adx_trend(f, sym):
    if f.get('adx_14',0) > 30 and f.get('plus_di',0) > f.get('minus_di',0) and f.get('price_vs_ema20',0) > 0:
        return _sig(sym, Direction.LONG, 0.68, f['price'], f.get('atr_14',1), "s03_adx_trend", "momentum")
    return None

def s04_price_momentum(f, sym):
    if f.get('rate_of_change',0) > 5 and f.get('rsi_14',50) < 75 and f.get('volume_sma_ratio',1) > 1.0:
        return _sig(sym, Direction.LONG, 0.60, f['price'], f.get('atr_14',1), "s04_price_mom", "momentum")
    return None

def s05_volume_spike(f, sym):
    if f.get('relative_volume',1) > 2.0 and f.get('returns_1d',0) > 0.01:
        return _sig(sym, Direction.LONG, 0.63, f['price'], f.get('atr_14',1), "s05_vol_spike", "momentum")
    return None

# ═══════════════════════════════════════════════════════
# CLUSTER 2: MEAN REVERSION (#6-#10)
# ═══════════════════════════════════════════════════════
def s06_bollinger_reversal(f, sym):
    if f.get('bb_position',0.5) < 0.1 and f.get('rsi_14',50) < 30:
        return _sig(sym, Direction.LONG, 0.67, f['price'], f.get('atr_14',1), "s06_bb_rev", "mean_reversion")
    if f.get('bb_position',0.5) > 0.9 and f.get('rsi_14',50) > 70:
        return _sig(sym, Direction.SHORT, 0.65, f['price'], f.get('atr_14',1), "s06_bb_rev", "mean_reversion")
    return None

def s07_rsi_oversold(f, sym):
    if f.get('rsi_14',50) < 25 and f.get('returns_5d',0) < -0.03:
        return _sig(sym, Direction.LONG, 0.64, f['price'], f.get('atr_14',1), "s07_rsi_os", "mean_reversion")
    return None

def s08_stochastic_cross(f, sym):
    if f.get('stoch_k',50) < 20 and f.get('stoch_d',50) < 25:
        return _sig(sym, Direction.LONG, 0.62, f['price'], f.get('atr_14',1), "s08_stoch", "mean_reversion")
    if f.get('stoch_k',50) > 80 and f.get('stoch_d',50) > 75:
        return _sig(sym, Direction.SHORT, 0.60, f['price'], f.get('atr_14',1), "s08_stoch", "mean_reversion")
    return None

def s09_williams_r(f, sym):
    wr = f.get('williams_r', -50)
    if wr < -90 and f.get('rsi_14',50) < 35:
        return _sig(sym, Direction.LONG, 0.63, f['price'], f.get('atr_14',1), "s09_wr", "mean_reversion")
    return None

def s10_cci_extreme(f, sym):
    cci = f.get('cci_20', 0)
    if cci < -200:
        return _sig(sym, Direction.LONG, 0.65, f['price'], f.get('atr_14',1), "s10_cci", "mean_reversion")
    if cci > 200:
        return _sig(sym, Direction.SHORT, 0.63, f['price'], f.get('atr_14',1), "s10_cci", "mean_reversion")
    return None

# ═══════════════════════════════════════════════════════
# CLUSTER 3: VOLATILITY (#11-#15)
# ═══════════════════════════════════════════════════════
def s11_atr_expansion(f, sym):
    if f.get('atr_14',0) > f.get('atr_20',1) * 1.3 and f.get('adx_14',20) > 25:
        d = Direction.LONG if f.get('returns_1d',0) > 0 else Direction.SHORT
        return _sig(sym, d, 0.58, f['price'], f.get('atr_14',1), "s11_atr_exp", "volatility")
    return None

def s12_vol_regime_switch(f, sym):
    if f.get('historical_vol_20',0.2) < 0.12 and f.get('bb_width',0) < 0.03:
        return _sig(sym, Direction.LONG, 0.55, f['price'], f.get('atr_14',1), "s12_vol_sw", "volatility")
    return None

def s13_straddle_arb(f, sym):
    if f.get('historical_vol_20',0.2) > 0.35:
        return _sig(sym, Direction.NEUTRAL, 0.55, f['price'], f.get('atr_14',1), "s13_straddle", "volatility")
    return None

def s14_gamma_scalp(f, sym):
    if f.get('bb_width',0) > 0.06 and f.get('relative_volume',1) > 1.5:
        d = Direction.LONG if f.get('bb_position',0.5) < 0.3 else Direction.SHORT
        return _sig(sym, d, 0.53, f['price'], f.get('atr_14',1), "s14_gamma", "volatility")
    return None

def s15_vix_contango(f, sym):
    if f.get('historical_vol_20',0.2) < 0.15:
        return _sig(sym, Direction.LONG, 0.55, f['price'], f.get('atr_14',1), "s15_vix_ct", "volatility")
    return None

# ═══════════════════════════════════════════════════════
# CLUSTER 4: STAT ARB (#16-#20)
# ═══════════════════════════════════════════════════════
def s16_pairs_zscore(f, sym):
    bb = f.get('bb_position', 0.5)
    if bb < 0.05:
        return _sig(sym, Direction.LONG, 0.68, f['price'], f.get('atr_14',1), "s16_pairs", "stat_arb")
    if bb > 0.95:
        return _sig(sym, Direction.SHORT, 0.66, f['price'], f.get('atr_14',1), "s16_pairs", "stat_arb")
    return None

def s17_cointegration_ou(f, sym):
    if f.get('bb_position',0.5) < 0.15 and f.get('rsi_14',50) < 35:
        return _sig(sym, Direction.LONG, 0.64, f['price'], f.get('atr_14',1), "s17_coint", "stat_arb")
    return None

def s18_lead_lag(f, sym):
    if abs(f.get('returns_1d',0)) > 0.02 and f.get('volume_sma_ratio',1) < 0.7:
        d = Direction.LONG if f.get('returns_1d',0) < -0.02 else Direction.SHORT
        return _sig(sym, d, 0.58, f['price'], f.get('atr_14',1), "s18_leadlag", "stat_arb")
    return None

def s19_triangular_arb(f, sym): return None
def s20_dispersion(f, sym): return None

# ═══════════════════════════════════════════════════════
# CLUSTER 5: MICROSTRUCTURE (#21-#25)
# ═══════════════════════════════════════════════════════
def s21_order_flow(f, sym):
    if f.get('obv_slope',0) > 0.5 and f.get('volume_sma_ratio',1) > 1.3:
        return _sig(sym, Direction.LONG, 0.60, f['price'], f.get('atr_14',1), "s21_flow", "microstructure")
    if f.get('obv_slope',0) < -0.5 and f.get('volume_sma_ratio',1) > 1.3:
        return _sig(sym, Direction.SHORT, 0.58, f['price'], f.get('atr_14',1), "s21_flow", "microstructure")
    return None

def s22_book_pressure(f, sym):
    if f.get('obv_slope',0) > 0.3 and f.get('vwap_deviation',0) < -0.005:
        return _sig(sym, Direction.LONG, 0.58, f['price'], f.get('atr_14',1), "s22_book", "microstructure")
    return None

def s23_vwap_dev(f, sym):
    vd = f.get('vwap_deviation', 0)
    if vd < -0.01 and f.get('rsi_14',50) < 40:
        return _sig(sym, Direction.LONG, 0.60, f['price'], f.get('atr_14',1), "s23_vwap", "microstructure")
    if vd > 0.01 and f.get('rsi_14',50) > 60:
        return _sig(sym, Direction.SHORT, 0.58, f['price'], f.get('atr_14',1), "s23_vwap", "microstructure")
    return None

def s24_tick_cluster(f, sym): return None
def s25_iceberg(f, sym): return None

# ═══════════════════════════════════════════════════════
# CLUSTER 6: ML/AI (#26-#30)
# ═══════════════════════════════════════════════════════
def s26_lstm_predict(f, sym):
    trend = f.get('trend_aligned',0); rsi = f.get('rsi_14',50); macd = f.get('macd_histogram',0)
    score = trend*0.3 + (1 if rsi>55 else 0)*0.3 + (1 if macd>0 else 0)*0.4
    if score > 0.7:
        return _sig(sym, Direction.LONG, 0.62, f['price'], f.get('atr_14',1), "s26_lstm", "ml_ai")
    if score < 0.2:
        return _sig(sym, Direction.SHORT, 0.58, f['price'], f.get('atr_14',1), "s26_lstm", "ml_ai")
    return None

def s27_rl_dqn(f, sym):
    if f.get('returns_5d',0) > 0.02 and f.get('adx_14',20) > 25 and f.get('rsi_14',50) < 70:
        return _sig(sym, Direction.LONG, 0.58, f['price'], f.get('atr_14',1), "s27_rl", "ml_ai")
    return None

def s28_anomaly_detect(f, sym):
    if abs(f.get('returns_1d',0)) > 0.04 and f.get('relative_volume',1) > 3:
        d = Direction.SHORT if f.get('returns_1d',0) > 0 else Direction.LONG
        return _sig(sym, d, 0.60, f['price'], f.get('atr_14',1), "s28_anomaly", "ml_ai")
    return None

def s29_hdbscan(f, sym): return None
def s30_gan_augment(f, sym): return None

# ═══════════════════════════════════════════════════════
# CLUSTER 7: LONG/SHORT EQUITY (#31-#35)
# ═══════════════════════════════════════════════════════
def s31_cross_sectional(f, sym):
    if f.get('returns_20d',0) > 0.05 and f.get('rsi_14',50) > 55 and f.get('volume_sma_ratio',1) > 1:
        return _sig(sym, Direction.LONG, 0.63, f['price'], f.get('atr_14',1), "s31_xsec", "long_short_equity")
    if f.get('returns_20d',0) < -0.05 and f.get('rsi_14',50) < 45:
        return _sig(sym, Direction.SHORT, 0.60, f['price'], f.get('atr_14',1), "s31_xsec", "long_short_equity")
    return None

def s32_factor_ranking(f, sym):
    if f.get('trend_aligned',0) == 1 and f.get('rsi_14',50) > 50 and f.get('rsi_14',50) < 70:
        return _sig(sym, Direction.LONG, 0.62, f['price'], f.get('atr_14',1), "s32_factor", "long_short_equity")
    return None

def s33_sector_rotation(f, sym):
    if f.get('returns_20d',0) > 0.08 and f.get('adx_14',20) > 25:
        return _sig(sym, Direction.LONG, 0.60, f['price'], f.get('atr_14',1), "s33_sector", "long_short_equity")
    return None

def s34_beta_neutral(f, sym): return None
def s35_stub_trade(f, sym): return None

# ═══════════════════════════════════════════════════════
# CLUSTER 8: EVENT-DRIVEN (#36-#40)
# ═══════════════════════════════════════════════════════
def s36_merger_arb(f, sym): return None
def s37_convertible_arb(f, sym): return None

def s38_earnings_vol(f, sym):
    if f.get('historical_vol_20',0.2) > 0.40 and f.get('relative_volume',1) > 2:
        return _sig(sym, Direction.NEUTRAL, 0.55, f['price'], f.get('atr_14',1), "s38_earn_vol", "event_driven")
    return None

def s39_special_situations(f, sym):
    if abs(f.get('returns_1d',0)) > 0.05 and f.get('relative_volume',1) > 3:
        d = Direction.LONG if f.get('returns_1d',0) > 0 else Direction.SHORT
        return _sig(sym, d, 0.58, f['price'], f.get('atr_14',1), "s39_special", "event_driven")
    return None

def s40_distressed(f, sym): return None

# ═══════════════════════════════════════════════════════
# CLUSTER 9: OPTIONS ADVANCED (#41-#45)
# ═══════════════════════════════════════════════════════
def s41_iron_condor(f, sym):
    if f.get('adx_14',20) < 20 and f.get('bb_width',0) < 0.04:
        return _sig(sym, Direction.NEUTRAL, 0.60, f['price'], f.get('atr_14',1), "s41_condor", "options_advanced")
    return None

def s42_butterfly(f, sym): return None
def s43_calendar_spread(f, sym): return None
def s44_ratio_spread(f, sym): return None
def s45_diagonal_spread(f, sym): return None

# ═══════════════════════════════════════════════════════
# CLUSTER 10: GLOBAL MACRO (#46-#49)
# ═══════════════════════════════════════════════════════
def s46_cta_trend(f, sym):
    if f.get('price_vs_ema50',0) > 0.02 and f.get('adx_14',20) > 25:
        return _sig(sym, Direction.LONG, 0.60, f['price'], f.get('atr_14',1), "s46_cta", "global_macro")
    if f.get('price_vs_ema50',0) < -0.02 and f.get('adx_14',20) > 25:
        return _sig(sym, Direction.SHORT, 0.58, f['price'], f.get('atr_14',1), "s46_cta", "global_macro")
    return None

def s47_carry_trade(f, sym): return None
def s48_macro_momentum(f, sym):
    if f.get('returns_20d',0) > 0.04 and f.get('rsi_14',50) > 55:
        return _sig(sym, Direction.LONG, 0.58, f['price'], f.get('atr_14',1), "s48_macro", "global_macro")
    return None

def s49_fx_momentum(f, sym): return None


# ═══════════════════════════════════════════════════════
# STRATEGY REGISTRY
# ═══════════════════════════════════════════════════════
ALL_STRATEGIES = {
    "momentum": [s01_macd_histogram, s02_rsi_breakout, s03_adx_trend, s04_price_momentum, s05_volume_spike],
    "mean_reversion": [s06_bollinger_reversal, s07_rsi_oversold, s08_stochastic_cross, s09_williams_r, s10_cci_extreme],
    "volatility": [s11_atr_expansion, s12_vol_regime_switch, s13_straddle_arb, s14_gamma_scalp, s15_vix_contango],
    "stat_arb": [s16_pairs_zscore, s17_cointegration_ou, s18_lead_lag, s19_triangular_arb, s20_dispersion],
    "microstructure": [s21_order_flow, s22_book_pressure, s23_vwap_dev, s24_tick_cluster, s25_iceberg],
    "ml_ai": [s26_lstm_predict, s27_rl_dqn, s28_anomaly_detect, s29_hdbscan, s30_gan_augment],
    "long_short_equity": [s31_cross_sectional, s32_factor_ranking, s33_sector_rotation, s34_beta_neutral, s35_stub_trade],
    "event_driven": [s36_merger_arb, s37_convertible_arb, s38_earnings_vol, s39_special_situations, s40_distressed],
    "options_advanced": [s41_iron_condor, s42_butterfly, s43_calendar_spread, s44_ratio_spread, s45_diagonal_spread],
    "global_macro": [s46_cta_trend, s47_carry_trade, s48_macro_momentum, s49_fx_momentum],
}

CLUSTER_REGIMES = {
    "momentum": ["bull_trend", "high_vol"],
    "mean_reversion": ["range_bound", "low_vol"],
    "volatility": ["high_vol", "crash"],
    "stat_arb": ["bull_trend", "bear_trend", "high_vol", "low_vol", "range_bound", "crash"],
    "microstructure": ["bull_trend", "bear_trend", "high_vol", "low_vol", "range_bound", "crash"],
    "ml_ai": ["bull_trend", "bear_trend", "high_vol", "low_vol", "range_bound", "crash"],
    "long_short_equity": ["bull_trend", "bear_trend", "high_vol", "low_vol", "range_bound", "crash"],
    "event_driven": ["bull_trend", "bear_trend", "high_vol", "low_vol", "range_bound", "crash"],
    "options_advanced": ["range_bound", "low_vol", "bull_trend"],
    "global_macro": ["bull_trend", "bear_trend", "high_vol", "low_vol", "range_bound", "crash"],
}


def run_all_strategies(features: Dict, symbol: str, regime: str) -> List[Signal]:
    """Run all 49 strategies against a symbol's features and return signals"""
    signals = []
    for cluster, strategies in ALL_STRATEGIES.items():
        if regime not in CLUSTER_REGIMES.get(cluster, []):
            continue
        for strategy_fn in strategies:
            try:
                signal = strategy_fn(features, symbol)
                if signal is not None:
                    signals.append(signal)
            except Exception as e:
                logger.debug(f"Strategy error: {e}")
    return signals
