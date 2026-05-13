"""
AlphaBot v4.0 — Prediction & Recommendation Engine
Forecasts next-day movement and generates actionable trade recommendations
by combining: 49 strategies + 8 AI agents + news sentiment + regime + technicals.
"""
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger("alphabot.predict")

# Indian market hours (IST)
MARKET_OPEN_HOUR = 9    # 9:15 AM IST
MARKET_CLOSE_HOUR = 15  # 3:30 PM IST


@dataclass
class StockPrediction:
    """Next-day prediction for a single stock"""
    symbol: str
    display: str
    exchange: str
    sector: str
    current_price: float

    # Prediction
    direction: str              # UP / DOWN / SIDEWAYS
    direction_probability: float  # 0-100
    predicted_range_low: float
    predicted_range_high: float
    predicted_target: float
    expected_move_pct: float

    # Entry/Exit
    action: str                 # BUY / SELL / AVOID
    entry_price: float
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    target_1: float             # 1st target (1R)
    target_2: float             # 2nd target (2R)
    target_3: float             # 3rd target (3R)
    risk_reward: float

    # Evidence
    ai_score: float             # 0-100
    news_sentiment: str         # BULLISH / BEARISH / NEUTRAL
    news_score: float
    regime_suitable: bool
    strategy_confirmations: int
    cluster_agreement: int

    # Catalysts
    key_reasons: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    news_headlines: List[str] = field(default_factory=list)

    # Meta
    confidence_grade: str = "C"  # A+ / A / B+ / B / C
    timeframe: str = "NEXT_DAY"
    generated_at: str = ""
    trend_strength: str = "WEAK"  # STRONG / MODERATE / WEAK

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().strftime("%Y-%m-%d %H:%M IST")
        self._compute_grade()

    def _compute_grade(self):
        score = 0
        if self.direction_probability >= 75: score += 3
        elif self.direction_probability >= 65: score += 2
        elif self.direction_probability >= 55: score += 1

        if self.risk_reward >= 3: score += 2
        elif self.risk_reward >= 2: score += 1

        if self.strategy_confirmations >= 8: score += 2
        elif self.strategy_confirmations >= 5: score += 1

        if self.news_sentiment == "BULLISH" and self.action == "BUY": score += 1
        elif self.news_sentiment == "BEARISH" and self.action == "SELL": score += 1

        if self.regime_suitable: score += 1

        if score >= 8: self.confidence_grade = "A+"
        elif score >= 6: self.confidence_grade = "A"
        elif score >= 4: self.confidence_grade = "B+"
        elif score >= 2: self.confidence_grade = "B"
        else: self.confidence_grade = "C"

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "display": self.display,
            "exchange": self.exchange,
            "sector": self.sector,
            "current_price": round(self.current_price, 2),
            "direction": self.direction,
            "direction_probability": round(self.direction_probability, 1),
            "predicted_range_low": round(self.predicted_range_low, 2),
            "predicted_range_high": round(self.predicted_range_high, 2),
            "predicted_target": round(self.predicted_target, 2),
            "expected_move_pct": round(self.expected_move_pct, 2),
            "action": self.action,
            "entry_price": round(self.entry_price, 2),
            "entry_zone_low": round(self.entry_zone_low, 2),
            "entry_zone_high": round(self.entry_zone_high, 2),
            "stop_loss": round(self.stop_loss, 2),
            "target_1": round(self.target_1, 2),
            "target_2": round(self.target_2, 2),
            "target_3": round(self.target_3, 2),
            "risk_reward": round(self.risk_reward, 2),
            "ai_score": round(self.ai_score, 1),
            "news_sentiment": self.news_sentiment,
            "news_score": round(self.news_score, 3),
            "regime_suitable": self.regime_suitable,
            "strategy_confirmations": self.strategy_confirmations,
            "cluster_agreement": self.cluster_agreement,
            "confidence_grade": self.confidence_grade,
            "trend_strength": self.trend_strength,
            "key_reasons": self.key_reasons,
            "risk_factors": self.risk_factors,
            "news_headlines": self.news_headlines,
            "timeframe": self.timeframe,
            "generated_at": self.generated_at
        }


@dataclass
class MarketOutlook:
    """Overall market prediction for tomorrow"""
    date: str
    nifty_direction: str
    nifty_probability: float
    nifty_range_low: float
    nifty_range_high: float
    nifty_target: float
    sentiment: str
    india_vix_outlook: str
    regime: str
    sector_rotation: List[Dict]
    macro_factors: List[str]
    key_risks: List[str]
    news_summary: str
    top_picks: List[str]     # Top 5 symbol recommendations
    avoid_list: List[str]    # Symbols to avoid
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().strftime("%Y-%m-%d %H:%M IST")

    def to_dict(self):
        return {
            "date": self.date,
            "nifty_direction": self.nifty_direction,
            "nifty_probability": round(self.nifty_probability, 1),
            "nifty_range_low": round(self.nifty_range_low, 2),
            "nifty_range_high": round(self.nifty_range_high, 2),
            "nifty_target": round(self.nifty_target, 2),
            "sentiment": self.sentiment,
            "india_vix_outlook": self.india_vix_outlook,
            "regime": self.regime,
            "sector_rotation": self.sector_rotation,
            "macro_factors": self.macro_factors,
            "key_risks": self.key_risks,
            "news_summary": self.news_summary,
            "top_picks": self.top_picks,
            "avoid_list": self.avoid_list,
            "generated_at": self.generated_at
        }


class PredictionEngine:
    """
    Generates next-day stock predictions and trade recommendations.
    Combines: technical features + AI agents + strategies + news sentiment.
    """

    def __init__(self, news_engine=None):
        self.news_engine = news_engine
        self.predictions: Dict[str, StockPrediction] = {}
        self.market_outlook: Optional[MarketOutlook] = None
        self.last_run: Optional[datetime] = None

    def predict_stock(
        self,
        symbol: str,
        features: Dict,
        agent_result: Dict,
        strategy_signals: list,
        market_data: Dict,
        regime: str
    ) -> Optional[StockPrediction]:
        """Generate next-day prediction for a single stock"""
        try:
            price = features.get('price', 0)
            if price <= 0:
                return None

            display = symbol.replace('.NS', '').replace('.BO', '')
            exchange = 'NSE' if symbol.endswith('.NS') else 'BSE'

            # ── 1. Technical Score ───────────────────────────
            tech_score = self._compute_technical_score(features)

            # ── 2. AI Agent Direction ───────────────────────
            agent_direction = agent_result.get('direction_prob', 0.5)
            agent_conf = agent_result.get('confidence', 0.5)
            ai_score = agent_result.get('composite_probability', 0.5) * 100

            # ── 3. Strategy Confirmations ────────────────────
            buy_signals = [s for s in strategy_signals if hasattr(s, 'direction') and s.direction.value == 'LONG']
            sell_signals = [s for s in strategy_signals if hasattr(s, 'direction') and s.direction.value == 'SHORT']
            n_confirmations = max(len(buy_signals), len(sell_signals))
            clusters_agreeing = len(set(s.cluster for s in strategy_signals if s.cluster))

            # ── 4. News Sentiment ────────────────────────────
            news_data = {"score": 0.0, "label": "NEUTRAL", "count": 0, "headlines": []}
            if self.news_engine:
                news_data = self.news_engine.get_symbol_sentiment(symbol)
            news_score = news_data['score']
            news_label = news_data['label']
            news_headlines = news_data.get('headlines', [])

            # ── 5. Regime Suitability ────────────────────────
            buy_regimes = ['bull_trend', 'low_vol', 'range_bound']
            sell_regimes = ['bear_trend', 'high_vol', 'crash']
            regime_suitable = regime in buy_regimes

            # ── 6. Candlestick & Chart Patterns (PDF Integration) ──
            candlestick_patterns = features.get('candlestick_patterns', [])
            chart_patterns = features.get('chart_patterns', [])
            all_patterns = candlestick_patterns + chart_patterns
            
            bull_patterns = ['Hammer', 'Inverted Hammer', 'Morning Star', 'Bullish Engulfing', 'Double Bottom', 'Resistance Breakout']
            bear_patterns = ['Hanging Man', 'Shooting Star', 'Evening Star', 'Bearish Engulfing', 'Double Top', 'Support Breakdown']
            
            pattern_score = 0.5
            bull_count = sum(1 for p in all_patterns if p in bull_patterns)
            bear_count = sum(1 for p in all_patterns if p in bear_patterns)
            
            if bull_count > bear_count: pattern_score = 0.7 + (bull_count * 0.05)
            elif bear_count > bull_count: pattern_score = 0.3 - (bear_count * 0.05)

            # ── 7. Composite Direction Probability ───────────
            # Weighted average of all signals
            weights = {
                'tech': 0.20,
                'agent': 0.25,
                'news': 0.15,
                'strategy': 0.15,
                'pattern': 0.15,
                'regime': 0.10
            }
            regime_score = 0.6 if regime_suitable else 0.4

            strategy_score = 0.5
            if n_confirmations > 0:
                buy_ratio = len(buy_signals) / max(n_confirmations, 1)
                strategy_score = buy_ratio

            composite = (
                tech_score * weights['tech'] +
                agent_direction * weights['agent'] +
                ((news_score + 1) / 2) * weights['news'] +
                strategy_score * weights['strategy'] +
                pattern_score * weights['pattern'] +
                regime_score * weights['regime']
            )
            composite = max(0.01, min(0.99, composite))

            # Direction and probability
            if composite > 0.57:
                direction = "UP"
                dir_prob = composite * 100
                action = "BUY"
            elif composite < 0.43:
                direction = "DOWN"
                dir_prob = (1 - composite) * 100
                action = "SELL SHORT"
            else:
                direction = "SIDEWAYS"
                dir_prob = 50 + abs(composite - 0.5) * 100
                action = "AVOID"

            # ── 7. Price Targets ─────────────────────────────
            atr = features.get('atr_14', price * 0.015)
            rsi = features.get('rsi_14', 50)
            bb_upper = features.get('bb_upper', price * 1.02)
            bb_lower = features.get('bb_lower', price * 0.98)
            support = features.get('support_level', price * 0.97)
            resistance = features.get('resistance_level', price * 1.03)

            if direction == "UP":
                # Entry near current price or slight dip
                entry = price * 0.998  # Slight discount
                entry_low = max(support, price - atr * 0.5)
                entry_high = price + atr * 0.3
                stop = max(support - atr * 0.3, price - atr * 1.5)
                risk = entry - stop
                t1 = entry + risk * 1.5
                t2 = entry + risk * 2.5
                t3 = min(resistance + atr, entry + risk * 4.0)
                predicted_high = price + atr * 2.0
                predicted_low = price - atr * 0.7
                predicted_target_price = t2

            elif direction == "DOWN":
                entry = price * 1.002
                entry_low = price - atr * 0.3
                entry_high = min(resistance, price + atr * 0.5)
                stop = min(resistance + atr * 0.3, price + atr * 1.5)
                risk = stop - entry
                t1 = entry - risk * 1.5
                t2 = entry - risk * 2.5
                t3 = max(support - atr, entry - risk * 4.0)
                predicted_high = price + atr * 0.7
                predicted_low = price - atr * 2.0
                predicted_target_price = t2

            else:  # SIDEWAYS
                entry = price
                entry_low = price - atr * 0.5
                entry_high = price + atr * 0.5
                stop = price - atr * 1.2
                t1 = price + atr * 0.8
                t2 = price + atr * 1.2
                t3 = resistance
                predicted_high = price + atr * 1.0
                predicted_low = price - atr * 1.0
                predicted_target_price = price
                risk = atr

            rr = abs(t2 - entry) / max(abs(entry - stop), 0.01)
            expected_move = ((predicted_target_price - price) / price) * 100

            # ── 8. Trend Strength ────────────────────────────
            adx = features.get('adx_14', 15)
            trend_strength = "STRONG" if adx > 30 else "MODERATE" if adx > 20 else "WEAK"

            # ── 9. Key Reasons & Risks ───────────────────────
            reasons, risks = self._build_reasons(
                features, direction, tech_score, agent_direction,
                agent_conf, news_label, regime, rsi, adx, n_confirmations
            )

            # ── 10. Sector from config ───────────────────────
            from config import SYMBOL_SECTOR_MAP
            sector = SYMBOL_SECTOR_MAP.get(symbol, "Unknown")

            pred = StockPrediction(
                symbol=symbol, display=display, exchange=exchange, sector=sector,
                current_price=price, direction=direction,
                direction_probability=dir_prob,
                predicted_range_low=predicted_low, predicted_range_high=predicted_high,
                predicted_target=predicted_target_price,
                expected_move_pct=expected_move,
                action=action,
                entry_price=entry, entry_zone_low=entry_low, entry_zone_high=entry_high,
                stop_loss=stop, target_1=t1, target_2=t2, target_3=t3,
                risk_reward=max(rr, 0),
                ai_score=ai_score, news_sentiment=news_label,
                news_score=news_score, regime_suitable=regime_suitable,
                strategy_confirmations=n_confirmations,
                cluster_agreement=clusters_agreeing,
                key_reasons=reasons, risk_factors=risks, news_headlines=news_headlines,
                trend_strength=trend_strength
            )
            return pred

        except Exception as e:
            logger.debug(f"Prediction error {symbol}: {e}")
            return None

    def _compute_technical_score(self, features: Dict) -> float:
        """Score 0-1 for bullish technical setup"""
        score = 0.5
        signals = 0

        rsi = features.get('rsi_14', 50)
        macd_hist = features.get('macd_histogram', 0)
        adx = features.get('adx_14', 15)
        plus_di = features.get('plus_di', 25)
        minus_di = features.get('minus_di', 25)
        bb_pos = features.get('bb_position', 0.5)
        vol_ratio = features.get('volume_ratio', 1.0)
        ema_slope = features.get('ema_slope', 0)
        stoch_k = features.get('stoch_k', 50)
        roc_5 = features.get('roc_5', 0)

        # RSI
        if 40 < rsi < 60: score += 0.0; signals += 1
        elif rsi < 35: score -= 0.15; signals += 1  # Oversold = bearish
        elif rsi > 65: score += 0.1; signals += 1   # Overbought = bullish momentum

        # MACD
        if macd_hist > 0: score += 0.15; signals += 1
        elif macd_hist < 0: score -= 0.15; signals += 1

        # ADX + DI
        if adx > 25 and plus_di > minus_di: score += 0.15; signals += 1
        elif adx > 25 and minus_di > plus_di: score -= 0.15; signals += 1

        # Bollinger
        if bb_pos > 0.7: score += 0.1; signals += 1   # Upper band = momentum
        elif bb_pos < 0.3: score -= 0.05; signals += 1  # Lower band = bearish

        # Volume
        if vol_ratio > 1.5: score += 0.1; signals += 1

        # EMA slope
        if ema_slope > 0: score += 0.1
        elif ema_slope < 0: score -= 0.1

        # Stochastic
        if stoch_k > 60: score += 0.05
        elif stoch_k < 40: score -= 0.05

        # ROC
        if roc_5 > 1: score += 0.05
        elif roc_5 < -1: score -= 0.05

        return max(0.01, min(0.99, score))

    def _build_reasons(self, features, direction, tech_score, agent_dir,
                       agent_conf, news_label, regime, rsi, adx, n_conf) -> tuple:
        reasons = []
        risks = []

        # Technical reasons
        macd = features.get('macd_histogram', 0)
        bb_pos = features.get('bb_position', 0.5)
        vol_ratio = features.get('volume_ratio', 1.0)
        ema_slope = features.get('ema_slope', 0)
        rsi_14 = features.get('rsi_14', 50)

        if macd > 0 and direction == "UP":
            reasons.append(f"MACD histogram positive (+{macd:.3f}) — bullish momentum")
        if macd < 0 and direction == "DOWN":
            reasons.append(f"MACD histogram negative ({macd:.3f}) — bearish pressure")

        if adx > 25:
            reasons.append(f"ADX={adx:.1f} — strong trending market, trade with trend")
        elif adx < 15:
            risks.append(f"ADX={adx:.1f} — weak trend, avoid breakout trades")

        if rsi_14 < 35:
            reasons.append(f"RSI={rsi_14:.1f} — oversold, potential reversal/bounce")
        elif rsi_14 > 70:
            reasons.append(f"RSI={rsi_14:.1f} — overbought, momentum play")
            risks.append("RSI overbought — risk of pullback")

        if vol_ratio > 1.8:
            reasons.append(f"Volume spike {vol_ratio:.1f}x avg — institutional activity")

        if ema_slope > 0 and direction == "UP":
            reasons.append("EMA slope positive — price above moving averages")
        elif ema_slope < 0 and direction == "DOWN":
            reasons.append("EMA slope negative — price below moving averages")

        # AI agent
        if agent_conf > 0.6:
            reasons.append(f"AI agents consensus: {agent_dir*100:.0f}% bullish (conf={agent_conf*100:.0f}%)")

        # Visual Chart Patterns (from PDF strategies)
        candlestick_patterns = features.get('candlestick_patterns', [])
        chart_patterns = features.get('chart_patterns', [])
        
        bull_patterns = ['Hammer', 'Inverted Hammer', 'Morning Star', 'Bullish Engulfing', 'Double Bottom', 'Resistance Breakout']
        bear_patterns = ['Hanging Man', 'Shooting Star', 'Evening Star', 'Bearish Engulfing', 'Double Top', 'Support Breakdown']
        
        for p in candlestick_patterns:
            if direction == "UP" and p in bull_patterns: reasons.append(f"Candlestick Strategy: {p} (Bullish Reversal)")
            elif direction == "DOWN" and p in bear_patterns: reasons.append(f"Candlestick Strategy: {p} (Bearish Reversal)")
            n_conf += 1  # Add pattern to strategy count
            
        for p in chart_patterns:
            if direction == "UP" and p in bull_patterns: reasons.append(f"Chart Pattern Strategy: {p} formed")
            elif direction == "DOWN" and p in bear_patterns: reasons.append(f"Chart Pattern Strategy: {p} formed")
            n_conf += 1  # Add pattern to strategy count

        # Strategy confirmations
        reasons.append(f"{n_conf} strategies/patterns confirmed from clusters")

        # News
        if news_label == "BULLISH":
            reasons.append("Positive news sentiment from financial media")
        elif news_label == "BEARISH":
            risks.append("Negative news flow — monitor for fundamental change")

        # Regime
        regime_labels = {
            'bull_trend': "Market in bull trend regime — favorable for longs",
            'bear_trend': "Market in bear trend — caution on long positions",
            'range_bound': "Range-bound market — look for support/resistance plays",
            'high_vol': "High volatility — use wider stops, smaller size",
            'low_vol': "Low volatility — potential for breakout",
            'crash': "Crash regime — defensive positioning recommended"
        }
        if regime in regime_labels:
            if direction == "UP" and regime in ['bull_trend', 'low_vol', 'range_bound']:
                reasons.append(regime_labels[regime])
            elif direction in ["DOWN", "SIDEWAYS"] and regime in ['bear_trend', 'high_vol', 'crash']:
                reasons.append(regime_labels[regime])
            else:
                risks.append(f"Regime ({regime}) may not favor this trade direction")

        return reasons[:5], risks[:3]

    def generate_market_outlook(
        self,
        nifty_features: Dict,
        india_vix: float,
        regime: str,
        market_sentiment: float,
        top_predictions: List[StockPrediction],
        news_engine=None
    ) -> MarketOutlook:
        """Generate tomorrow's overall market outlook"""

        nifty_price = nifty_features.get('price', 23000)
        nifty_rsi = nifty_features.get('rsi_14', 50)
        nifty_adx = nifty_features.get('adx_14', 20)
        nifty_macd = nifty_features.get('macd_histogram', 0)
        atr = nifty_features.get('atr_14', nifty_price * 0.01)

        # Overall direction
        bullish_score = 0
        if nifty_rsi > 55: bullish_score += 1
        if nifty_macd > 0: bullish_score += 2
        if india_vix < 18: bullish_score += 1
        if regime == 'bull_trend': bullish_score += 2
        if market_sentiment > 0.1: bullish_score += 1

        bearish_score = 0
        if nifty_rsi < 45: bearish_score += 1
        if nifty_macd < 0: bearish_score += 2
        if india_vix > 22: bearish_score += 1
        if regime in ['bear_trend', 'crash']: bearish_score += 2
        if market_sentiment < -0.1: bearish_score += 1

        if bullish_score > bearish_score + 1:
            nifty_dir = "BULLISH"
            nifty_prob = 55 + min(bullish_score * 3, 25)
            nifty_target = nifty_price + atr * 1.5
            nifty_low = nifty_price - atr * 0.5
            nifty_high = nifty_price + atr * 2.0
        elif bearish_score > bullish_score + 1:
            nifty_dir = "BEARISH"
            nifty_prob = 55 + min(bearish_score * 3, 25)
            nifty_target = nifty_price - atr * 1.5
            nifty_low = nifty_price - atr * 2.0
            nifty_high = nifty_price + atr * 0.5
        else:
            nifty_dir = "NEUTRAL"
            nifty_prob = 50
            nifty_target = nifty_price
            nifty_low = nifty_price - atr
            nifty_high = nifty_price + atr

        # VIX outlook
        if india_vix > 25: vix_outlook = "HIGH — expect elevated volatility, wider ranges"
        elif india_vix > 18: vix_outlook = "MODERATE — normal volatility expected"
        else: vix_outlook = "LOW — range-bound, look for breakouts"

        # Sector rotation
        sector_scores = {}
        for pred in top_predictions:
            sec = pred.sector
            if sec not in sector_scores:
                sector_scores[sec] = []
            sector_scores[sec].append(pred.ai_score)

        sector_rotation = [
            {"sector": sec, "avg_score": round(np.mean(scores), 1), "count": len(scores)}
            for sec, scores in sector_scores.items()
            if len(scores) >= 2
        ]
        sector_rotation.sort(key=lambda x: x['avg_score'], reverse=True)

        # Macro factors
        macro_factors = []
        if news_engine and news_engine.macro_news:
            macro_factors = [n.title[:80] for n in news_engine.macro_news[:4]]

        macro_factors = macro_factors or [
            "RBI policy stance — monitor repo rate direction",
            "FII/DII flow data — key market driver",
            "Global cues: US markets, crude oil price",
            "INR/USD movement — affects IT and export stocks"
        ]

        # Key risks
        key_risks = []
        if india_vix > 22:
            key_risks.append(f"India VIX elevated at {india_vix:.1f} — high uncertainty")
        if regime in ['bear_trend', 'crash']:
            key_risks.append("Bearish regime — avoid aggressive longs")
        if market_sentiment < -0.2:
            key_risks.append("Negative news sentiment dominating market")
        key_risks.append("Global risk-off sentiment can trigger sudden sell-off")

        # Top picks
        buy_preds = [p for p in top_predictions if p.action == "BUY" and p.confidence_grade in ['A+','A','B+']]
        buy_preds.sort(key=lambda x: (x.direction_probability, x.risk_reward), reverse=True)
        top_picks = [p.display for p in buy_preds[:5]]

        avoid_preds = [p for p in top_predictions if p.action in ["SELL SHORT", "AVOID"] or p.confidence_grade == "C"]
        avoid_list = [p.display for p in avoid_preds[:3]]

        # News summary
        if news_engine and news_engine.news_cache:
            recent_high = [n for n in news_engine.news_cache[:10] if n.impact == 'HIGH']
            news_summary = " | ".join([n.title[:60] for n in recent_high[:3]]) if recent_high else "No high-impact news today"
        else:
            news_summary = "News feed initializing..."

        tomorrow = (date.today() + timedelta(days=1)).strftime("%d-%b-%Y")
        # Skip weekends
        tomorrow_dt = date.today() + timedelta(days=1)
        if tomorrow_dt.weekday() == 5: tomorrow_dt += timedelta(days=2)  # Saturday → Monday
        elif tomorrow_dt.weekday() == 6: tomorrow_dt += timedelta(days=1)
        tomorrow = tomorrow_dt.strftime("%d-%b-%Y (%A)")

        outlook = MarketOutlook(
            date=tomorrow,
            nifty_direction=nifty_dir,
            nifty_probability=nifty_prob,
            nifty_range_low=nifty_low,
            nifty_range_high=nifty_high,
            nifty_target=nifty_target,
            sentiment="BULLISH" if market_sentiment > 0.1 else "BEARISH" if market_sentiment < -0.1 else "NEUTRAL",
            india_vix_outlook=vix_outlook,
            regime=regime,
            sector_rotation=sector_rotation[:8],
            macro_factors=macro_factors[:5],
            key_risks=key_risks[:4],
            news_summary=news_summary,
            top_picks=top_picks,
            avoid_list=avoid_list
        )

        self.market_outlook = outlook
        return outlook

    def get_top_recommendations(self, n: int = 10) -> List[Dict]:
        """Get top N actionable recommendations sorted by grade and R:R"""
        grade_order = {'A+': 5, 'A': 4, 'B+': 3, 'B': 2, 'C': 1}
        preds = list(self.predictions.values())
        preds = [p for p in preds if p.action in ["BUY", "SELL SHORT"]]
        preds.sort(key=lambda p: (grade_order.get(p.confidence_grade, 0), p.risk_reward), reverse=True)
        return [p.to_dict() for p in preds[:n]]

    def get_all_predictions(self) -> List[Dict]:
        return [p.to_dict() for p in sorted(
            self.predictions.values(),
            key=lambda p: p.direction_probability,
            reverse=True
        )]
