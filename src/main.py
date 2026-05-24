#!/usr/bin/env python3
"""
Hermes Trading System - Main Orchestrator
"""
import os
import sys
import time
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

# Dodaj workspace do path
sys.path.insert(0, "/home/r00t/hermes-trading")

load_dotenv("/home/r00t/hermes-trading/config/.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("/home/r00t/hermes-trading/logs/service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    logger.info("=== Hermes Trading System uruchomiony ===")
    
    # Import modułów
    try:
        from src.brain import TradingBrain
        from src.treasury import Treasury
        from src.risk import RiskManager
        from src.executor import TradingExecutor
        
        brain = TradingBrain()
        treasury = Treasury()
        risk = RiskManager()
        executor = TradingExecutor()
        
        logger.info("Wszystkie moduły zainicjalizowane")
        
        # Główna pętla
        while True:
            try:
                # Pobierz dane
                df = brain.fetch_data()
                if df is not None:
                    analysis = brain.analyze_technical(df)
                    signal = brain.generate_signal(analysis)
                    logger.info(f"Sygnał: {signal}")
                
                time.sleep(300)  # 5 minut
                
            except KeyboardInterrupt:
                logger.info("Zatrzymano przez użytkownika")
                break
            except Exception as e:
                logger.error(f"Błąd cyklu: {e}")
                time.sleep(60)
    
    except Exception as e:
        logger.error(f"Błąd inicjalizacji: {e}")
        raise

if __name__ == "__main__":
    main()
