#!/usr/bin/env python3
"""
Hermes Trading System - Main Orchestrator
Główny moduł koordynujący wszystkich agentów
"""
import os
import sys
import time
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("/home/r00t/hermes-trading/config/.env")

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("/home/r00t/hermes-trading/logs/hermes.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HermesOrchestrator:
    """Główny orchestrator systemu Hermes"""
    
    def __init__(self):
        self.brain = None
        self.treasury = None
        self.risk_manager = None
        self.executor = None
        self.is_running = False
        self.cycle_count = 0
        
    def initialize(self):
        """Inicjalizacja wszystkich modułów"""
        logger.info("=== Inicjalizacja Hermes Trading System ===")
        
        try:
            from src.brain import TradingBrain
            from src.treasury import Treasury
            from src.risk import RiskManager
            from src.executor import TradingExecutor
            
            self.brain = TradingBrain()
            self.treasury = Treasury()
            self.risk_manager = RiskManager()
            self.executor = TradingExecutor()
            
            logger.info("Wszystkie moduły zainicjalizowane")
            return True
        except Exception as e:
            logger.error(f"Błąd inicjalizacji: {e}")
            return False
    
    def run_cycle(self):
        """Jeden cykl decyzyjny"""
        self.cycle_count += 1
        logger.info(f"=== Cykl #{self.cycle_count} ===")
        
        try:
            # 1. Pobierz dane
            df = self.brain.fetch_data()
            
            # 2. Analiza techniczna
            analysis = self.brain.analyze_technical(df)
            
            # 3. Generuj sygnał
            signal = self.brain.generate_signal(analysis)
            
            # 4. Ocena ryzyka
            risk_check = self.risk_manager.validate_trade(
                signal, 
                self.treasury.current_capital,
                self.treasury.positions
            )
            
            # 5. Wykonaj transakcję (jeśli zatwierdzona)
            if risk_check["approved"] and signal["signal"] != "HOLD":
                position_size = self.treasury.get_position_size()
                self.executor.execute_order(
                    signal["signal"].lower(),
                    self.brain.pair,
                    position_size
                )
            
            # 6. Sprawdź stop-loss/take-profit
            if analysis:
                self.treasury.check_stop_loss(analysis["price"])
                self.treasury.check_take_profit(analysis["price"])
            
            # 7. Raport
            summary = self.treasury.get_portfolio_summary()
            logger.info(f"Raport: {json.dumps(summary, indent=2)}")
            
        except Exception as e:
            logger.error(f"Błąd cyklu: {e}")
    
    def run(self):
        """Główna pętla"""
        logger.info("=== Hermes Trading System uruchomiony ===")
        self.is_running = True
        
        while self.is_running:
            self.run_cycle()
            time.sleep(300)  # 5 minut
    
    def stop(self):
        """Zatrzymaj system"""
        self.is_running = False
        logger.info("Hermes zatrzymany")

if __name__ == "__main__":
    hermes = HermesOrchestrator()
    if hermes.initialize():
        hermes.run()
    else:
        logger.error("Nie udało się zainicjalizować Hermesa")
        sys.exit(1)
