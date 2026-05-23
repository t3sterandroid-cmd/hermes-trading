#!/usr/bin/env python3
"""Hermes Trading System - Executor"""
import os, json, logging
from datetime import datetime
from dotenv import load_dotenv
import ccxt
load_dotenv("/home/r00t/hermes-trading/config/.env")
logger = logging.getLogger(__name__)

class TradingExecutor:
    def __init__(self):
        self.exchange = None
        self.exchange_id = os.getenv("EXCHANGE", "binance")
        self.is_test_mode = os.getenv("TEST_MODE", "true").lower() == "true"
        self.trade_log = []
    def connect(self, api_key=None, api_secret=None):
        try:
            exchange_class = getattr(ccxt, self.exchange_id)
            config = {"apiKey": api_key or os.getenv("API_KEY"), "secret": api_secret or os.getenv("API_SECRET"), "enableRateLimit": True, "options": {"defaultType": "spot"}}
            if self.is_test_mode: config["sandbox"] = True
            self.exchange = exchange_class(config)
            self.exchange.load_markets()
            logger.info(f"Połączono z {self.exchange_id}")
            return True
        except Exception as e:
            logger.error(f"Błąd połączenia: {e}")
            return False
    def execute_order(self, side, symbol, amount, order_type="market", price=None):
        if self.is_test_mode:
            logger.info(f"[TEST] {side} {amount} {symbol}")
            return {"id": "test", "status": "test"}
        try:
            if order_type == "market":
                order = self.exchange.create_market_buy_order(symbol, amount) if side == "buy" else self.exchange.create_market_sell_order(symbol, amount)
            else:
                order = self.exchange.create_limit_buy_order(symbol, amount, price) if side == "buy" else self.exchange.create_limit_sell_order(symbol, amount, price)
            self.trade_log.append(order)
            return order
        except Exception as e:
            logger.error(f"Błąd zlecenia: {e}")
            return None
