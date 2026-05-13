"""
AlphaBot v4.0 — Paper Trading Execution Engine
Simulates order execution with realistic slippage and fills.
"""
import numpy as np
from typing import Dict, List, Optional
from core.models import Signal, Position, Trade, Direction, PortfolioState
from datetime import datetime
import uuid, logging

logger = logging.getLogger("alphabot.execution")


class PaperTrader:
    """Paper trading engine with simulated execution (INR)"""

    def __init__(self, initial_capital: float = 50_000_000.0):
        self.initial_capital = initial_capital
        self.portfolio = PortfolioState(equity=initial_capital, cash=initial_capital, peak_equity=initial_capital)
        self.positions: List[Position] = []
        self.trade_history: List[Trade] = []
        self.daily_returns: List[float] = []
        self._prev_equity = initial_capital

    def execute_signal(self, signal: Signal, position_value: float) -> Optional[Position]:
        """Execute a signal as a paper trade"""
        if position_value <= 0 or signal.entry_price <= 0:
            return None

        # Simulate slippage (0.01-0.05%)
        slippage = np.random.uniform(0.0001, 0.0005)
        if signal.direction == Direction.LONG:
            fill_price = signal.entry_price * (1 + slippage)
        else:
            fill_price = signal.entry_price * (1 - slippage)

        quantity = max(1, int(position_value / fill_price))
        cost = quantity * fill_price

        if cost > self.portfolio.cash * 0.8:
            quantity = max(1, int(self.portfolio.cash * 0.8 / fill_price))
            cost = quantity * fill_price

        if cost > self.portfolio.cash or quantity <= 0:
            return None

        # Create position
        position = Position(
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=quantity,
            entry_price=fill_price,
            current_price=fill_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            strategy_id=signal.strategy_id,
            signal_id=signal.signal_id,
            entry_time=datetime.utcnow().isoformat()
        )

        self.positions.append(position)
        self.portfolio.cash -= cost
        self._update_portfolio()

        sym_display = signal.symbol.replace('.NS','').replace('.BO','')
        logger.info(f"OPENED {signal.direction.value} {quantity} {sym_display} @ Rs.{fill_price:.2f} [{signal.strategy_id}]")
        return position

    def update_prices(self, prices: Dict[str, float]):
        """Update positions with current prices"""
        for pos in self.positions:
            if pos.symbol in prices:
                pos.update_price(prices[pos.symbol])

        self._check_exits(prices)
        self._update_portfolio()

    def _check_exits(self, prices: Dict[str, float]):
        """Check stop loss and take profit for all positions"""
        to_close = []
        for pos in self.positions:
            price = prices.get(pos.symbol, pos.current_price)
            reason = None

            if pos.direction == Direction.LONG:
                if price <= pos.stop_loss:
                    reason = "STOP_LOSS"
                elif price >= pos.take_profit:
                    reason = "TAKE_PROFIT"
            elif pos.direction == Direction.SHORT:
                if price >= pos.stop_loss:
                    reason = "STOP_LOSS"
                elif price <= pos.take_profit:
                    reason = "TAKE_PROFIT"

            # Trailing stop (Chandelier exit at 3x ATR approximation)
            if pos.direction == Direction.LONG:
                trail_stop = pos.highest_price * 0.97  # ~3% trail
                if price < trail_stop and price > pos.stop_loss:
                    reason = "TRAILING_STOP"
            else:
                trail_stop = pos.lowest_price * 1.03
                if price > trail_stop and price < pos.stop_loss:
                    reason = "TRAILING_STOP"

            if reason:
                to_close.append((pos, reason, price))

        for pos, reason, price in to_close:
            self._close_position(pos, price, reason)

    def _close_position(self, position: Position, exit_price: float, reason: str):
        """Close a position and record the trade"""
        slippage = np.random.uniform(0.0001, 0.0003)
        if position.direction == Direction.LONG:
            actual_exit = exit_price * (1 - slippage)
            pnl = (actual_exit - position.entry_price) * position.quantity
        else:
            actual_exit = exit_price * (1 + slippage)
            pnl = (position.entry_price - actual_exit) * position.quantity

        pnl_pct = pnl / (position.entry_price * position.quantity) * 100

        trade = Trade(
            trade_id=str(uuid.uuid4())[:8],
            symbol=position.symbol,
            direction=position.direction,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=actual_exit,
            pnl=pnl,
            pnl_pct=pnl_pct,
            strategy_id=position.strategy_id,
            entry_time=position.entry_time,
            exit_time=datetime.utcnow().isoformat(),
            exit_reason=reason,
            slippage=slippage
        )

        self.trade_history.append(trade)
        self.portfolio.cash += position.quantity * actual_exit
        self.portfolio.total_pnl += pnl

        if pnl > 0:
            self.portfolio.winning_trades += 1
        else:
            self.portfolio.losing_trades += 1
        self.portfolio.total_trades += 1

        self.positions = [p for p in self.positions if p.position_id != position.position_id]

        result = "[WIN]" if pnl > 0 else "[LOSS]"
        sym_display = position.symbol.replace('.NS','').replace('.BO','')
        logger.info(f"{result} CLOSED {sym_display} [{reason}] PnL: Rs.{pnl:.0f} ({pnl_pct:.1f}%)")

    def close_all(self, prices: Dict[str, float], reason: str = "MANUAL_CLOSE"):
        """Emergency close all positions"""
        for pos in list(self.positions):
            price = prices.get(pos.symbol, pos.current_price)
            self._close_position(pos, price, reason)

    def _update_portfolio(self):
        """Recalculate portfolio state"""
        pos_value = sum(p.current_price * p.quantity for p in self.positions)
        long_val = sum(p.current_price * p.quantity for p in self.positions if p.direction == Direction.LONG)
        short_val = sum(p.current_price * p.quantity for p in self.positions if p.direction == Direction.SHORT)
        unrealized = sum(p.unrealized_pnl for p in self.positions)

        self.portfolio.positions_value = pos_value
        self.portfolio.equity = self.portfolio.cash + pos_value
        self.portfolio.long_exposure = long_val / max(self.portfolio.equity, 1)
        self.portfolio.short_exposure = short_val / max(self.portfolio.equity, 1)
        self.portfolio.net_exposure = self.portfolio.long_exposure - self.portfolio.short_exposure
        self.portfolio.gross_exposure = self.portfolio.long_exposure + self.portfolio.short_exposure
        self.portfolio.num_positions = len(self.positions)
        self.portfolio.total_pnl_pct = (self.portfolio.equity / self.initial_capital - 1) * 100

        # Drawdown
        self.portfolio.peak_equity = max(self.portfolio.peak_equity, self.portfolio.equity)
        self.portfolio.drawdown = self.portfolio.peak_equity - self.portfolio.equity
        self.portfolio.drawdown_pct = self.portfolio.drawdown / self.portfolio.peak_equity if self.portfolio.peak_equity > 0 else 0

        # Win rate
        if self.portfolio.total_trades > 0:
            self.portfolio.win_rate = self.portfolio.winning_trades / self.portfolio.total_trades

        # Daily PnL
        self.portfolio.daily_pnl = self.portfolio.equity - self._prev_equity

        # Sharpe (rolling)
        daily_ret = (self.portfolio.equity - self._prev_equity) / max(self._prev_equity, 1)
        self.daily_returns.append(daily_ret)
        if len(self.daily_returns) > 2:
            returns = np.array(self.daily_returns[-30:])
            if np.std(returns) > 0:
                self.portfolio.sharpe_ratio = float(np.mean(returns) / np.std(returns) * np.sqrt(252))

    def new_day(self):
        """Reset daily tracking"""
        self._prev_equity = self.portfolio.equity
        self.portfolio.daily_pnl = 0

    def get_recent_trades(self, n: int = 50) -> List[Dict]:
        return [t.to_dict() for t in self.trade_history[-n:]]

    def get_positions(self) -> List[Dict]:
        return [p.to_dict() for p in self.positions]
