#!/usr/bin/env python3
"""
Hermes Trading System - Watchdog
Zewnętrzny monitor który restartuje agenta w przypadku awarii
Uruchamiany na niezależnym serwerze lub jako osobny proces
"""
import os
import time
import json
import subprocess
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

class Watchdog:
    """Monitoruje stan agenta i restartuje w przypadku awarii"""
    
    def __init__(self, check_interval=60, max_failures=3):
        self.check_interval = check_interval
        self.max_failures = max_failures
        self.failure_count = 0
        self.last_check = None
        self.agent_healthy = True
        self.log = []
    
    def check_agent_health(self):
        """Sprawdź czy agent odpowiada"""
        try:
            # Proste sprawdzenie — czy proces istnieje
            result = subprocess.run(["pgrep", "-f", "hermes"], capture_output=True)
            is_running = result.returncode == 0
            
            self.last_check = datetime.now().isoformat()
            
            if is_running:
                self.failure_count = 0
                self.agent_healthy = True
                return True
            else:
                self.failure_count += 1
                self.agent_healthy = False
                logger.warning(f"Agent nie odpowiada! Próba {self.failure_count}/{self.max_failures}")
                return False
                
        except Exception as e:
            logger.error(f"Błąd sprawdzenia: {e}")
            return False
    
    def restart_agent(self):
        """Restartuj agenta"""
        logger.info("Restartowanie agenta...")
        try:
            subprocess.run(["systemctl", "restart", "hermes-trading"], check=True)
            self.failure_count = 0
            self.agent_healthy = True
            return True
        except Exception as e:
            logger.error(f"Błąd restartu: {e}")
            return False
    
    def run(self):
        """Główna pętla watchdog"""
        logger.info("Watchdog uruchomiony")
        
        while True:
            if not self.check_agent_health():
                if self.failure_count >= self.max_failures:
                    self.restart_agent()
            
            time.sleep(self.check_interval)
