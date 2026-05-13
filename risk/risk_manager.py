"""
AlphaBot v4.0 — Risk Management Engine
Kelly sizing, VaR, circuit breakers per PRD FR-RISK-001 through FR-RISK-006.
"""
import numpy as np
from typing import Dict, List
from core.models import Signal, PortfolioState, CircuitState
import logging

logger = logging.getLogger("alphabot.risk")


class RiskManager:
    """Unified risk management: position sizing, VaR, circuit breakers"""

    def __init__(self, config=None):
        from config import RISK, TRADING
        self.risk = config or RISK
        self.trading = TRADING
        self.daily_pnl = 0.0
        self.circuit_state = CircuitState.CLOSED
        self.strategy_pnls: Dict[str, float] = {}

    def size_position(self, signal: Signal, portfolio: PortfolioState, strategy_stats: Dict = None) -> float:
        """Calculate position size using Kelly Criterion (FR-RISK-001)"""
        if self.circuit_state == CircuitState.OPEN:
            return 0.0

        # Default stats if none available
        if not strategy_stats:
            strategy_stats = {'win_rate': 0.55, 'avg_win': 0.015, 'avg_loss': 0.01}

        p = strategy_stats['win_rate']
        q = 1 - p
        b = strategy_stats['avg_win'] / max(strategy_stats['avg_loss'], 0.001)

        # Kelly fraction
        kelly = (p * b - q) / b if b > 0 else 0
        kelly = max(kelly, 0)

        # Quarter Kelly for safety
        position_pct = self.trading.kelly_fraction * kelly

        # Volatility targeting
        if portfolio.drawdown_pct > 0.05:
            position_pct *= 0.5  # Halve size during drawdown
        
        # Regime adjustment
        if portfolio.regime == 'crash':
            position_pct *= 0.2
        elif portfolio.regime == 'high_vol':
            position_pct *= 0.7
        elif portfolio.regime == 'low_vol':
            position_pct *= 1.15

        # Caps
        position_pct = min(position_pct, self.trading.max_position_pct)
        position_pct = max(position_pct, 0.005)  # Min 0.5%

        # Cash check
        available = portfolio.cash * (1 - self.trading.cash_reserve_pct)
        position_value = min(position_pct * portfolio.equity, available)

        return max(position_value, 0)

    def check_circuit_breakers(self, portfolio: PortfolioState) -> Dict:
        """Check all circuit breakers (FR-RISK-002)"""
        results = {'trading_allowed': True, 'breakers': {}}

        # Daily loss limit
        daily_pnl_pct = portfolio.daily_pnl / max(portfolio.equity, 1)
        if daily_pnl_pct < -self.risk.daily_loss_limit:
            results['trading_allowed'] = False
            results['breakers']['daily_loss'] = f"Daily loss {daily_pnl_pct:.2%} exceeds limit {-self.risk.daily_loss_limit:.2%}"
            self.circuit_state = CircuitState.OPEN

        # VIX circuit breaker
        vix_limit = getattr(self.risk, 'india_vix_circuit_breaker', getattr(self.risk, 'vix_circuit_breaker', 40.0))
        if portfolio.vix > vix_limit:
            results['trading_allowed'] = False
            results['breakers']['vix'] = f"India VIX {portfolio.vix:.1f} exceeds threshold {vix_limit}"
            self.circuit_state = CircuitState.OPEN

        # Correlation circuit breaker
        if portfolio.avg_correlation > self.risk.correlation_circuit_breaker:
            results['trading_allowed'] = False
            results['breakers']['correlation'] = f"Avg correlation {portfolio.avg_correlation:.2f} exceeds {self.risk.correlation_circuit_breaker}"

        # Gross exposure
        if portfolio.gross_exposure > self.risk.max_gross_exposure:
            results['trading_allowed'] = False
            results['breakers']['exposure'] = f"Gross exposure {portfolio.gross_exposure:.1%} exceeds {self.risk.max_gross_exposure:.1%}"

        return results

    def calculate_var(self, positions: List[Dict], returns_data: Dict[str, np.ndarray]) -> Dict:
        """Monte Carlo VaR (FR-RISK-003)"""
        if not positions:
            return {'var': 0, 'cvar': 0, 'var_pct': 0}

        n_sims = min(self.risk.var_simulations, 5000)
        portfolio_pnl = np.zeros(n_sims)
        total_value = sum(p.get('value', 0) for p in positions)

        for pos in positions:
            symbol = pos.get('symbol', '')
            value = pos.get('value', 0)
            returns = returns_data.get(symbol, np.random.normal(0, 0.02, 20))
            
            if len(returns) > 0:
                sim_returns = np.random.choice(returns, size=n_sims, replace=True)
                portfolio_pnl += value * sim_returns

        var_threshold = np.percentile(portfolio_pnl, (1 - self.risk.var_confidence) * 100)
        cvar = portfolio_pnl[portfolio_pnl <= var_threshold].mean() if np.any(portfolio_pnl <= var_threshold) else var_threshold

        return {
            'var': float(-var_threshold),
            'cvar': float(-cvar),
            'var_pct': float(-var_threshold / total_value) if total_value > 0 else 0,
            'simulations': n_sims,
            'confidence': self.risk.var_confidence
        }

    def validate_signal(self, signal: Signal, portfolio: PortfolioState) -> Dict:
        """Validate a signal against risk rules"""
        issues = []
        
        if self.circuit_state == CircuitState.OPEN:
            issues.append("Circuit breaker is OPEN - trading halted")

        if portfolio.num_positions >= 20:
            issues.append("Maximum positions reached (20)")

        if signal.confidence < self.trading.min_confidence:
            issues.append(f"Confidence {signal.confidence:.2f} below minimum {self.trading.min_confidence}")

        if signal.stop_loss <= 0:
            issues.append("Invalid stop loss")

        return {'valid': len(issues) == 0, 'issues': issues}
