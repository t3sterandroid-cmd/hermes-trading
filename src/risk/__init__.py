#!/usr/bin/env python3
"""
Hermes Trading System - Risk Manager
Zarządzanie ryzykiem zgodne ze specyfikacją PDF
"""
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class RiskManager:
    """Ocena i zarządzanie ryzykiem"""
    
    def __init__(self):
        self.max_leverage = 2  # Max 1:2 dźwignia (z PDF)
        self.max_risk_per_trade = 0.01  # 1% kapitału
        self.max_daily_loss = 0.05  # 5% dzienny limit strat
        self.max_drawdown = 0.15  # 15% max drawdown
        self.daily_pnl = 0.0
        self.last_reset = datetime.now().date()
        self.risk_log = []
    
    def validate_trade(self, signal, portfolio_value, current_positions):
        """Sprawdź czy transakcja jest bezpieczna"""
        reasons = []
        approved = True
        
        # Sprawdź dzienny limit strat
        if self.daily_pnl < -portfolio_value * self.max_daily_loss:
            reasons.append(f"Dzienny limit strat osiągnięty: {self.daily_pnl:.2f}")
            approved = False
        
        # Sprawdź liczbę otwartych pozycji
        if len(current_positions) >= 5:
            reasons.append(f"Za dużo otwartych pozycji: {len(current_positions)}")
            approved = False
        
        # Sprawdź dźwignię
        total_exposure = sum(p.get("amount", 0) for p in current_positions)
        if total_exposure > portfolio_value * self.max_leverage / 100:
            reasons.append(f"Przekroczona dźwignia: {total_exposure:.2f}")
            approved = False
        
        result = {
            "approved": approved,
            "reasons": reasons,
            "timestamp": datetime.now().isoformat(),
            "signal": signal
        }
        
        self.risk_log.append(result)
        return result
    
    def update_daily_pnl(self, pnl):
        """Aktualizuj dzienny PnL"""
        today = datetime.now().date()
        if today != self.last_reset:
            self.daily_pnl = 0.0
            self.last_reset = today
        self.daily_pnl += pnl
    
    def get_risk_report(self):
        """Raport ryzyka"""
        return {
            "daily_pnl": self.daily_pnl,
            "max_risk_per_trade": self.max_risk_per_trade,
            "max_leverage": self.max_leverage,
            "max_daily_loss": self.max_daily_loss,
            "max_drawdown": self.max_drawdown,
            "last_reset": str(self.last_reset),
            "risk_events": len(self.risk_log),
            "timestamp": datetime.now().isoformat()
        }
