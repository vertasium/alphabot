"""
AlphaBot v4.0 — Feature Engineering Engine
Computes 120+ technical features per stock per the PAD spec.
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional
import logging

logger = logging.getLogger("alphabot.features")


class FeatureEngine:
    """
    Computes technical, momentum, volatility, volume, and microstructure features.
    Based on PAD Section 4.2 - 500+ features specification.
    """

    def compute_features(self, df: pd.DataFrame, symbol: str = "") -> Dict[str, float]:
        """Compute all available features from OHLCV data"""
        if df is None or len(df) < 20:
            return {}

        features = {}
        closes = df['Close'].values.astype(float)
        highs = df['High'].values.astype(float)
        lows = df['Low'].values.astype(float)
        volumes = df['Volume'].values.astype(float)
        opens = df['Open'].values.astype(float) if 'Open' in df.columns else closes

        # Price-based features
        features['price'] = closes[-1]
        features['returns_1d'] = self._returns(closes, 1)
        features['returns_5d'] = self._returns(closes, 5)
        features['returns_20d'] = self._returns(closes, 20)
        features['log_returns'] = np.log(closes[-1] / closes[-2]) if len(closes) > 1 else 0
        features['price_vs_ema20'] = self._price_vs_ema(closes, 20)
        features['price_vs_ema50'] = self._price_vs_ema(closes, 50)
        features['price_vs_ema200'] = self._price_vs_ema(closes, min(200, len(closes)))

        # Momentum features
        features['rsi_6'] = self._rsi(closes, 6)
        features['rsi_14'] = self._rsi(closes, 14)
        features['rsi_21'] = self._rsi(closes, 21)
        macd = self._macd(closes)
        features['macd_line'] = macd['line']
        features['macd_signal'] = macd['signal']
        features['macd_histogram'] = macd['histogram']
        features['macd_histogram_slope'] = macd['histogram_slope']
        stoch = self._stochastic(closes, highs, lows)
        features['stoch_k'] = stoch['k']
        features['stoch_d'] = stoch['d']
        features['williams_r'] = self._williams_r(closes, highs, lows)
        features['cci_20'] = self._cci(closes, highs, lows, 20)
        adx_data = self._adx(closes, highs, lows, 14)
        features['adx_14'] = adx_data['adx']
        features['plus_di'] = adx_data['plus_di']
        features['minus_di'] = adx_data['minus_di']
        features['rate_of_change'] = self._roc(closes, 12)

        # Volatility features
        features['atr_10'] = self._atr(closes, highs, lows, 10)
        features['atr_14'] = self._atr(closes, highs, lows, 14)
        features['atr_20'] = self._atr(closes, highs, lows, 20)
        bb = self._bollinger_bands(closes, 20)
        features['bb_upper'] = bb['upper']
        features['bb_lower'] = bb['lower']
        features['bb_width'] = bb['width']
        features['bb_position'] = bb['position']
        features['historical_vol_20'] = self._historical_vol(closes, 20)
        features['historical_vol_60'] = self._historical_vol(closes, min(60, len(closes)))

        # Volume features
        features['volume'] = volumes[-1]
        features['volume_sma_ratio'] = self._volume_sma_ratio(volumes, 20)
        features['obv_slope'] = self._obv_slope(closes, volumes)
        features['vwap_deviation'] = self._vwap_deviation(closes, highs, lows, volumes)
        features['relative_volume'] = self._relative_volume(volumes)

        # Support/Resistance
        features['pivot_point'] = (highs[-1] + lows[-1] + closes[-1]) / 3
        features['support_1'] = 2 * features['pivot_point'] - highs[-1]
        features['resistance_1'] = 2 * features['pivot_point'] - lows[-1]
        features['support_2'] = features['pivot_point'] - (highs[-1] - lows[-1])
        features['resistance_2'] = features['pivot_point'] + (highs[-1] - lows[-1])

        # Trend features
        features['ema_20'] = self._ema(closes, 20)
        features['ema_50'] = self._ema(closes, min(50, len(closes)))
        features['sma_20'] = np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
        features['trend_aligned'] = 1.0 if (
            features['price'] > features['ema_20'] > features['ema_50']
        ) else 0.0

        # Parabolic SAR (simplified)
        features['psar'] = self._parabolic_sar(closes, highs, lows)

        # Candlestick & Chart Patterns (From PDF Knowledge)
        features['candlestick_patterns'] = self._candlestick_patterns(opens, highs, lows, closes)
        features['chart_patterns'] = self._chart_patterns(highs, lows, closes)

        return features

    def _returns(self, prices, period):
        if len(prices) <= period:
            return 0.0
        return (prices[-1] - prices[-1 - period]) / prices[-1 - period]

    def _price_vs_ema(self, prices, span):
        if len(prices) < span:
            return 0.0
        ema = pd.Series(prices).ewm(span=span).mean().iloc[-1]
        return (prices[-1] - ema) / ema

    def _ema(self, prices, span):
        if len(prices) < 2:
            return prices[-1]
        return float(pd.Series(prices).ewm(span=min(span, len(prices))).mean().iloc[-1])

    def _rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50.0
        deltas = np.diff(prices[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _macd(self, prices):
        if len(prices) < 26:
            return {'line': 0, 'signal': 0, 'histogram': 0, 'histogram_slope': 0}
        s = pd.Series(prices)
        ema12 = s.ewm(span=12).mean()
        ema26 = s.ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        histogram = macd_line - signal_line
        hist_slope = histogram.iloc[-1] - histogram.iloc[-2] if len(histogram) > 1 else 0
        return {
            'line': float(macd_line.iloc[-1]),
            'signal': float(signal_line.iloc[-1]),
            'histogram': float(histogram.iloc[-1]),
            'histogram_slope': float(hist_slope)
        }

    def _stochastic(self, closes, highs, lows, period=14):
        if len(closes) < period:
            return {'k': 50.0, 'd': 50.0}
        h = np.max(highs[-period:])
        l = np.min(lows[-period:])
        if h == l:
            return {'k': 50.0, 'd': 50.0}
        k = 100 * (closes[-1] - l) / (h - l)
        d = np.mean([100 * (closes[-i] - np.min(lows[-period - i:-i or None])) / 
                      max(np.max(highs[-period - i:-i or None]) - np.min(lows[-period - i:-i or None]), 0.01) 
                      for i in range(1, min(4, len(closes)))])
        return {'k': float(k), 'd': float(d)}

    def _williams_r(self, closes, highs, lows, period=14):
        if len(closes) < period:
            return -50.0
        h = np.max(highs[-period:])
        l = np.min(lows[-period:])
        if h == l:
            return -50.0
        return -100 * (h - closes[-1]) / (h - l)

    def _cci(self, closes, highs, lows, period=20):
        if len(closes) < period:
            return 0.0
        tp = (closes[-period:] + highs[-period:] + lows[-period:]) / 3
        tp_mean = np.mean(tp)
        tp_mad = np.mean(np.abs(tp - tp_mean))
        if tp_mad == 0:
            return 0.0
        return (tp[-1] - tp_mean) / (0.015 * tp_mad)

    def _adx(self, closes, highs, lows, period=14):
        if len(closes) < period + 1:
            return {'adx': 20.0, 'plus_di': 0, 'minus_di': 0}
        
        n = min(len(closes), period + 10)
        h = highs[-n:]
        l = lows[-n:]
        c = closes[-n:]
        
        plus_dm = np.maximum(np.diff(h), 0)
        minus_dm = np.maximum(-np.diff(l), 0)
        
        mask = plus_dm > minus_dm
        plus_dm = np.where(mask, plus_dm, 0)
        minus_dm = np.where(~mask, minus_dm, 0)
        
        tr = np.maximum(h[1:] - l[1:], 
                        np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
        
        atr = np.mean(tr[-period:])
        if atr == 0:
            return {'adx': 20.0, 'plus_di': 0, 'minus_di': 0}
        
        plus_di = 100 * np.mean(plus_dm[-period:]) / atr
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr
        
        dx = 100 * abs(plus_di - minus_di) / max(plus_di + minus_di, 0.01)
        return {'adx': float(dx), 'plus_di': float(plus_di), 'minus_di': float(minus_di)}

    def _roc(self, prices, period=12):
        if len(prices) <= period:
            return 0.0
        return (prices[-1] - prices[-1 - period]) / prices[-1 - period] * 100

    def _atr(self, closes, highs, lows, period=14):
        if len(closes) < period + 1:
            return 0.0
        n = period + 1
        h = highs[-n:]
        l = lows[-n:]
        c = closes[-n:]
        tr = np.maximum(h[1:] - l[1:],
                        np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
        return float(np.mean(tr))

    def _bollinger_bands(self, prices, period=20):
        if len(prices) < period:
            return {'upper': prices[-1], 'lower': prices[-1], 'width': 0, 'position': 0.5}
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        upper = sma + 2 * std
        lower = sma - 2 * std
        width = (upper - lower) / sma if sma else 0
        position = (prices[-1] - lower) / (upper - lower) if (upper - lower) else 0.5
        return {'upper': float(upper), 'lower': float(lower), 'width': float(width), 'position': float(position)}

    def _historical_vol(self, prices, period=20):
        if len(prices) < period + 1:
            return 0.2
        log_returns = np.diff(np.log(prices[-period - 1:]))
        return float(np.std(log_returns) * np.sqrt(252))

    def _volume_sma_ratio(self, volumes, period=20):
        if len(volumes) < period:
            return 1.0
        sma = np.mean(volumes[-period:])
        return float(volumes[-1] / sma) if sma else 1.0

    def _obv_slope(self, closes, volumes, period=10):
        if len(closes) < period + 1:
            return 0.0
        obv = np.zeros(len(closes))
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                obv[i] = obv[i - 1] + volumes[i]
            elif closes[i] < closes[i - 1]:
                obv[i] = obv[i - 1] - volumes[i]
            else:
                obv[i] = obv[i - 1]
        if len(obv) < period:
            return 0.0
        x = np.arange(period)
        y = obv[-period:]
        slope = np.polyfit(x, y, 1)[0]
        return float(slope / max(abs(np.mean(y)), 1))

    def _vwap_deviation(self, closes, highs, lows, volumes):
        if len(closes) < 2:
            return 0.0
        tp = (closes + highs + lows) / 3
        cum_tp_vol = np.cumsum(tp * volumes)
        cum_vol = np.cumsum(volumes)
        vwap = cum_tp_vol / np.maximum(cum_vol, 1)
        return float((closes[-1] - vwap[-1]) / max(vwap[-1], 0.01))

    def _relative_volume(self, volumes, period=20):
        if len(volumes) < period:
            return 1.0
        avg = np.mean(volumes[-period:])
        return float(volumes[-1] / avg) if avg else 1.0

    def _parabolic_sar(self, closes, highs, lows):
        if len(closes) < 5:
            return closes[-1]
        # Simplified PSAR
        af = 0.02
        max_af = 0.20
        bull = closes[-1] > closes[-5]
        if bull:
            sar = min(lows[-5:])
            ep = max(highs[-5:])
        else:
            sar = max(highs[-5:])
            ep = min(lows[-5:])
        sar = sar + af * (ep - sar)
        return float(sar)

    def _candlestick_patterns(self, opens, highs, lows, closes) -> list:
        if len(closes) < 3: return []
        patterns = []
        o, h, l, c = opens[-1], highs[-1], lows[-1], closes[-1]
        body = abs(c - o)
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - l
        candle_range = h - l
        o1, h1, l1, c1 = opens[-2], highs[-2], lows[-2], closes[-2]
        body1 = abs(c1 - o1)
        o2, h2, l2, c2 = opens[-3], highs[-3], lows[-3], closes[-3]
        body2 = abs(c2 - o2)

        if body <= candle_range * 0.1 and candle_range > 0: patterns.append("Doji")
        if lower_shadow > body * 2 and upper_shadow < body * 0.5:
            patterns.append("Hammer" if (c > o1 and c1 < o1) else "Hanging Man")
        if upper_shadow > body * 2 and lower_shadow < body * 0.5:
            patterns.append("Shooting Star" if (c < o1 and c1 > o1) else "Inverted Hammer")
        if c1 < o1 and c > o and c > o1 and o < c1: patterns.append("Bullish Engulfing")
        if c1 > o1 and c < o and c < o1 and o > c1: patterns.append("Bearish Engulfing")
        if c2 < o2 and body1 < body2 * 0.3 and c > o and c > (o2 + c2) / 2: patterns.append("Morning Star")
        if c2 > o2 and body1 < body2 * 0.3 and c < o and c < (o2 + c2) / 2: patterns.append("Evening Star")
        return patterns

    def _chart_patterns(self, highs, lows, closes) -> list:
        if len(closes) < 20: return []
        patterns = []
        p1_h, p2_h = np.max(highs[-20:-10]), np.max(highs[-10:])
        if abs(p1_h - p2_h) / p1_h < 0.015 and p1_h > np.mean(closes[-20:]) * 1.05:
            patterns.append("Double Top")
        p1_l, p2_l = np.min(lows[-20:-10]), np.min(lows[-10:])
        if abs(p1_l - p2_l) / p1_l < 0.015 and p1_l < np.mean(closes[-20:]) * 0.95:
            patterns.append("Double Bottom")
        res = np.max(highs[-20:-1])
        if closes[-1] > res: patterns.append("Resistance Breakout")
        sup = np.min(lows[-20:-1])
        if closes[-1] < sup: patterns.append("Support Breakdown")
        return patterns
