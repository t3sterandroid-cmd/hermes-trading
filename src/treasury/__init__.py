#!/usr/bin/env python3
"""
Hermes Trading System - Treasury (Skarbiec)
Moduł zarządzania kapitałem zgodny ze specyfikacją PDF:
- 70% Kapitał Pracujący (Trading)
- 20% Fundusz Przetrwania (Sustenance)
- 10% Fundusz Ekspansji (Evolution)
"""
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("/home/r00t/hermes-trading/config/.env")
logger = logging.getLogger(__name__)

# Alokacja zgodna z PDF
ALLOCATION = {
    "trading": 0.70,      # Kapitał Pracujący
    "sustenance": 0.20,   # Fundusz Przetrwania
    "evolution": 0.10,    # Fundusz Ekspansji
}

# Reguły z PDF
MAX_RISK_PER_TRADE = 0.01  # 1% kapitału na transakcję
SHARPE_THRESHOLD = 1.5      # Minimum Sharpe Ratio dla replikacji
REPLICATION_THRESHOLD = 5000  # USD dla replikacji

class Treasury:
    """Zarządzanie kapitałem Hermesa"""
    
    def __init__(self, initial_capital=None):
        self.initial_capital = initial_capital or float(os.getenv("INITIAL_CAPITAL", 1000))
        self.current_capital = self.initial_capital
        self.allocated = {
            "trading": self.initial_capital * ALLOCATION["trading"],
            "sustenance": self.initial_capital * ALLOCATION["sustenance"],
            "evolution": self.initial_capital * ALLOCATION["evolution"],
        }
        self.positions = []
        self.trade_history = []
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_capital = self.initial_capital
        
    def get_position_size(self):
        """Oblicz wielkość pozycji (1% z kapitału pracującego)"""
        return self.allocated["trading"] * MAX_RISK_PER_TRADE
    
    def can_open_position(self, amount):
        """Sprawdź czy można otworzyć pozycję"""
        if amount > self.allocated["trading"]:
            logger.warning(f"Brak środków: potrzeba {amount}, dostępne {self.allocated['trading']}")
            return False
        if amount <= 0:
            logger.warning(f"Nieprawidłowa kwota: {amount}")
            return False
        return True
    
    def open_position(self, side, amount, price):
        """Otwórz pozycję"""
        if not self.can_open_position(amount):
            return None
        
        position = {
            "id": len(self.positions) + 1,
            "side": side,
            "amount": amount,
            "entry_price": price,
            "stop_loss": price * (1 - float(os.getenv("STOP_LOSS_PCT", 3)) / 100),
            "take_profit": price * (1 + float(os.getenv("TAKE_PROFIT_PCT", 15)) / 100),
            "opened_at": datetime.now().isoformat(),
            "pnl": 0.0
        }
        
        self.allocated["trading"] -= amount
        self.positions.append(position)
        
        logger.info(f"Otwarto pozycję {side}: ${amount:.2f} @ ${price:.2f}")
        return position
    
    def close_position(self, position_id, close_price):
        """Zamknij pozycję"""
        for pos in self.positions:
            if pos["id"] == position_id:
                if pos["side"] == "BUY":
                    pnl = (close_price - pos["entry_price"]) * pos["amount"]
                else:
                    pnl = (pos["entry_price"] - close_price) * pos["amount"]
                
                pos["pnl"] = pnl
                pos["closed_at"] = datetime.now().isoformat()
                pos["close_price"] = close_price
                
                self.positions.remove(pos)
                self.trade_history.append(pos)
                self.total_pnl += pnl
                self.allocated["trading"] += pos["amount"] + pnl
                
                logger.info(f"Zamknięto pozycję #{position_id}: PnL=${pnl:.2f}")
                return pos
        
        logger.warning(f"Nie znaleziono pozycji #{position_id}")
        return None
    
    def check_stop_loss(self, current_price):
        """Sprawdź stop-loss dla wszystkich pozycji"""
        closed = []
        for pos in self.positions:
            if pos["side"] == "BUY" and current_price <= pos["stop_loss"]:
                closed.append(self.close_position(pos["id"], current_price))
            elif pos["side"] == "SELL" and current_price >= pos["stop_loss"]:
                closed.append(self.close_position(pos["id"], current_price))
        return closed
    
    def check_take_profit(self, current_price):
        """Sprawdź take-profit dla wszystkich pozycji"""
        closed = []
        for pos in self.positions:
            if pos["side"] == "BUY" and current_price >= pos["take_profit"]:
                closed.append(self.close_position(pos["id"], current_price))
            elif pos["side"] == "SELL" and current_price <= pos["take_profit"]:
                closed.append(self.close_position(pos["id"], current_price))
        return closed
    
    def get_portfolio_summary(self):
        """Podsumowanie portfela"""
        total_value = sum(self.allocated.values())
        
        # Licz Sharpe Ratio (uproszczona)
        if len(self.trade_history) > 10:
            returns = [t["pnl"] / t["amount"] for t in self.trade_history]
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe = 0
        
        summary = {
            "total_value": total_value,
            "initial_capital": self.initial_capital,
            "total_pnl": self.total_pnl,
            "return_pct": ((total_value - self.initial_capital) / self.initial_capital) * 100,
            "allocated": self.allocated,
            "open_positions": len(self.positions),
            "closed_trades": len(self.trade_history),
            "sharpe_ratio": sharpe,
            "can_replicate": (
                self.allocated["evolution"] >= REPLICATION_THRESHOLD and
                sharpe >= SHARPE_THRESHOLD
            ),
            "timestamp": datetime.now().isoformat()
        }
        
        return summary
    
    def rebalance(self):
        """Przywróć alokację 70/20/10"""
        total = sum(self.allocated.values())
        self.allocated = {
            "trading": total * ALLOCATION["trading"],
            "sustenance": total * ALLOCATION["sustenance"],
            "evolution": total * ALLOCATION["evolution"],
        }
        logger.info(f"Rebalansowanie: Trading=${self.allocated['trading']:.2f}, "
                    f"Sustenance=${self.allocated['sustenance']:.2f}, "
                    f"Evolution=${self.allocated['evolution']:.2f}")


if __name__ == "__main__":
    import numpy as np
    
    t = Treasury(1000)
    print("=== Hermes Treasury ===")
    print(f"Kapitał początkowy: ${t.initial_capital:.2f}")
    print(f"Alokacja: Trading=${t.allocated['trading']:.2f}, "
          f"Sustenance=${t.allocated['sustenance']:.2f}, "
          f"Evolution=${t.allocated['evolution']:.2f}")
    print(f"Wielkość pozycji: ${t.get_position_size():.2f}")
    
    summary = t.get_portfolio_summary()
    print(f"\nPodsumowanie: {json.dumps(summary, indent=2)}")
