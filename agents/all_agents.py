"""
AlphaBot v4.0 — AI Agents (All 8 + Coordinator)
Simplified implementations using numpy (no GPU required).
"""
import numpy as np
from typing import Dict, List
from core.models import AgentPrediction
import logging

logger = logging.getLogger("alphabot.agents")


class TrendAgent:
    def __init__(self): self.name = "trend"
    def predict(self, f: Dict, m: Dict = None) -> AgentPrediction:
        s = 0.5 + np.clip(f.get('price_vs_ema20',0)*5,-0.15,0.15) + np.clip(f.get('price_vs_ema50',0)*3,-0.1,0.1)
        s += np.clip(f.get('macd_histogram',0)*100,-0.1,0.1) + np.clip((f.get('rsi_14',50)-50)/100,-0.1,0.1)
        c = min(0.95, 0.3 + f.get('adx_14',20)/100 + abs(np.clip(s,0.05,0.95)-0.5))
        return AgentPrediction(agent_name=self.name, direction_probability=float(np.clip(s,0.05,0.95)),
            confidence=float(c), predicted_return=float(f.get('returns_5d',0)*2),
            rationale=f"EMA:{'↑' if f.get('price_vs_ema20',0)>0 else '↓'} MACD:{'↑' if f.get('macd_histogram',0)>0 else '↓'} RSI:{f.get('rsi_14',50):.0f}")


class VolatilityAgent:
    def __init__(self): self.name = "volatility"
    def predict(self, f: Dict, m: Dict = None) -> AgentPrediction:
        vix = m.get('vix',15) if m else 15
        s = 0.5 + (0.1 if vix<15 else (-0.15 if vix>30 else (-0.3 if vix>40 else 0)))
        regime = "low_vol" if vix<15 else ("high_vol" if vix>30 else ("crash" if vix>40 else "normal"))
        return AgentPrediction(agent_name=self.name, direction_probability=float(np.clip(s,0.1,0.9)),
            confidence=float(min(0.9, 0.4+abs(vix-20)/40)), regime=regime, rationale=f"VIX:{vix:.1f} Regime:{regime}")


class MicrostructureAgent:
    def __init__(self): self.name = "microstructure"
    def predict(self, f: Dict, m: Dict = None) -> AgentPrediction:
        s = 0.5 + np.clip(f.get('obv_slope',0)*2,-0.15,0.15) + np.clip(-f.get('vwap_deviation',0)*5,-0.1,0.1)
        c = min(0.8, 0.3 + abs(f.get('obv_slope',0))*3)
        return AgentPrediction(agent_name=self.name, direction_probability=float(np.clip(s,0.1,0.9)),
            confidence=float(max(0.2,c)), rationale=f"OBV:{'↑' if f.get('obv_slope',0)>0 else '↓'} VWAP:{f.get('vwap_deviation',0):.3f}")


class SentimentAgent:
    def __init__(self): self.name = "sentiment"
    def predict(self, f: Dict, m: Dict = None) -> AgentPrediction:
        s = 0.5 + np.clip(f.get('returns_1d',0)*10,-0.1,0.1) + np.clip(f.get('returns_5d',0)*5,-0.1,0.1)
        rsi = f.get('rsi_14',50)
        if rsi > 80: s -= 0.1
        elif rsi < 20: s += 0.1
        return AgentPrediction(agent_name=self.name, direction_probability=float(np.clip(s,0.1,0.9)),
            confidence=0.5, rationale=f"Momentum:{s:.2f} RSI:{rsi:.0f}")


class CorrelationAgent:
    def __init__(self): self.name = "correlation"
    def predict(self, f: Dict, m: Dict = None) -> AgentPrediction:
        bb = f.get('bb_position',0.5); wr = f.get('williams_r',-50)
        s = 0.5 + (0.15 if bb<0.2 else (-0.15 if bb>0.8 else 0)) + (0.1 if wr<-80 else (-0.1 if wr>-20 else 0))
        return AgentPrediction(agent_name=self.name, direction_probability=float(np.clip(s,0.1,0.9)),
            confidence=float(max(0.2,min(0.75,abs(bb-0.5)*1.5))),
            metadata={'cointegration_strength': float(1-abs(bb-0.5))}, rationale=f"BB:{bb:.2f} WR:{wr:.0f}")


class FactorAgent:
    def __init__(self): self.name = "factor"
    def predict(self, f: Dict, m: Dict = None) -> AgentPrediction:
        fs = np.clip(50 + f.get('trend_aligned',0)*15 + (f.get('rsi_14',50)-50)/5 + min((f.get('volume_sma_ratio',1)-1)*10,10),0,100)
        d = 0.5 + (fs-50)/200
        return AgentPrediction(agent_name=self.name, direction_probability=float(np.clip(d,0.15,0.85)),
            confidence=float(min(0.7,fs/150)), metadata={'composite_score': float(fs)}, rationale=f"Factor:{fs:.0f}/100")


class EventAgent:
    def __init__(self): self.name = "event"
    def predict(self, f: Dict, m: Dict = None) -> AgentPrediction:
        ep = min(0.8, abs(f.get('returns_1d',0))*20 + max(f.get('relative_volume',1)-2,0)*0.2)
        return AgentPrediction(agent_name=self.name, direction_probability=0.5, confidence=float(min(0.6,ep)),
            metadata={'event_probability': float(ep)}, rationale=f"Event prob:{ep:.1%}")


class OptionsAgent:
    def __init__(self): self.name = "options"
    def predict(self, f: Dict, m: Dict = None) -> AgentPrediction:
        vix = m.get('vix',15) if m else 15
        iv_rank = min(100,max(0,(vix-10)/30*100)); s = 0.5 + (-0.05 if iv_rank>70 else (0.05 if iv_rank<30 else 0))
        return AgentPrediction(agent_name=self.name, direction_probability=float(s),
            confidence=float(min(0.6,iv_rank/200+0.2)), metadata={'iv_rank': float(iv_rank)}, rationale=f"IVR:{iv_rank:.0f}")


class AgentCoordinator:
    """Meta-agent: combines all 8 agent predictions (PRD FR-AI-009)"""
    def __init__(self):
        self.agents = {'trend': TrendAgent(), 'volatility': VolatilityAgent(), 'microstructure': MicrostructureAgent(),
            'sentiment': SentimentAgent(), 'correlation': CorrelationAgent(), 'factor': FactorAgent(),
            'event': EventAgent(), 'options': OptionsAgent()}
        self.weights = {'trend':0.25,'volatility':0.15,'microstructure':0.12,'sentiment':0.10,
            'correlation':0.12,'factor':0.12,'event':0.07,'options':0.07}

    def predict_all(self, features: Dict, market_data: Dict = None) -> Dict:
        preds = {}
        for n, a in self.agents.items():
            try: preds[n] = a.predict(features, market_data)
            except: preds[n] = AgentPrediction(agent_name=n, direction_probability=0.5, confidence=0.0)

        ws, tw = 0, 0
        for n, p in preds.items():
            w = self.weights.get(n,0.1) * p.confidence
            ws += p.direction_probability * w; tw += w

        cp = ws / tw if tw > 0 else 0.5
        action = "BUY" if cp >= 0.65 else ("SELL" if cp <= 0.35 else "HOLD")
        return {'action': action, 'composite_probability': float(cp),
            'confidence': float(np.mean([p.confidence for p in preds.values()])),
            'predictions': {k: {'direction': v.direction_probability, 'confidence': v.confidence,
                'rationale': v.rationale} for k, v in preds.items()}}
