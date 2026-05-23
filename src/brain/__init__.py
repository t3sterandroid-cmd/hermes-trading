#!/usr/bin/env python3
"""
Hermes Trading System - Brain (Rdzeń Analityczno-Decyzyjny)
Moduł odpowiedzialny za:
- Zebranie danych rynkowych (OHLCV, orderbook, sentyment)
- Generowanie sygnałów transakcyjnych
- Podejmowanie decyzji przez RL + LLM ensemble
"""
import os
import json
import time
import logging
import hashlib
from datetime import datetime
from dotenv import load_dotenv
import ccxt
import pandas as pd
import numpy as np

load_dotenv("/home/r00t/hermes-trading/config/.env")

logger = logging.getLogger(__name__)

class TradingBrain:
    """Główny moduł decyzyjny Hermesa"""
    
    def __init__(self):
        self.pair = os.getenv("TRADING_PAIR", "BTC/USDC")
        self.timeframe = os.getenv("TIMEFRAME", "1h")
        self.max_position_pct = float(os.getenv("MAX_POSITION_PCT", 10)) / 100
        self.stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", 3)) / 100
        self.take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", 15)) / 100
        self.exchange = None
        self.last_decision = None
        self.decision_history = []
        
    def connect_exchange(self, exchange_id="binance", api_key=None, api_secret=None):
        """Połącz z giełdą"""
        try:
            exchange_class = getattr(ccxt, exchange_id)
            config = {
                "apiKey": api_key or os.getenv("API_KEY"),
                "secret": api_secret or os.getenv("API_SECRET"),
                "enableRateLimit": True,
                "options": {"defaultType": "spot"}
            }
            self.exchange = exchange_class(config)
            self.exchange.load_markets()
            logger.info(f"Połączono z {exchange_id}")
            return True
        except Exception as e:
            logger.error(f"Błąd połączenia: {e}")
            return False
    
    def fetch_data(self, limit=100):
        """Zebrane dane OHLCV"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.pair, self.timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            logger.info(f"Pobrano {len(df)} świec dla {self.pair}")
            return df
        except Exception as e:
            logger.error(f"Błąd pobierania danych: {e}")
            return None
    
    def analyze_technical(self, df):
        """Analiza techniczna"""
        if df is None or len(df) < 50:
            return None
        
        # SMA
        df["sma_20"] = df["close"].rolling(20).mean()
        df["sma_50"] = df["close"].rolling(50).mean()
        
        # EMA
        df["ema_12"] = df["close"].ewm(span=12).mean()
        df["ema_26"] = df["close"].ewm(span=26).mean()
        df["macd"] = df["ema_12"] - df["ema_26"]
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        
        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        df["bb_mid"] = df["close"].rolling(20).mean()
        df["bb_std"] = df["close"].rolling(20).std()
        df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
        df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]
        
        # ATR (Average True Range)
        df["hl"] = df["high"] - df["low"]
        df["hc"] = abs(df["high"] - df["close"].shift())
        df["lc"] = abs(df["low"] - df["close"].shift())
        df["tr"] = df[["hl", "hc", "lc"]].max(axis=1)
        df["atr"] = df["tr"].rolling(14).mean()
        
        last = df.iloc[-1]
        
        analysis = {
            "price": float(last["close"]),
            "sma_20": float(last["sma_20"]) if not pd.isna(last["sma_20"]) else None,
            "sma_50": float(last["sma_50"]) if not pd.isna(last["sma_50"]) else None,
            "rsi": float(last["rsi"]) if not pd.isna(last["rsi"]) else None,
            "macd": float(last["macd"]) if not pd.isna(last["macd"]) else None,
            "macd_signal": float(last["macd_signal"]) if not pd.isna(last["macd_signal"]) else None,
            "bb_upper": float(last["bb_upper"]) if not pd.isna(last["bb_upper"]) else None,
            "bb_lower": float(last["bb_lower"]) if not pd.isna(last["bb_lower"]) else None,
            "atr": float(last["atr"]) if not pd.isna(last["atr"]) else None,
            "volume": float(last["volume"]),
            "timestamp": str(last["timestamp"])
        }
        
        return analysis
    
    def generate_signal(self, analysis):
        """Generowanie sygnału transakcyjnego"""
        if analysis is None:
            return {"signal": "HOLD", "confidence": 0.0, "reasons": ["Brak danych"]}
        
        signals = []
        confidence = 0.0
        reasons = []
        
        # SMA crossover
        if analysis["sma_20"] and analysis["sma_50"]:
            if analysis["sma_20"] > analysis["sma_50"]:
                signals.append(1)
                confidence += 0.2
                reasons.append("SMA20 > SMA50 (bullish)")
            else:
                signals.append(-1)
                confidence += 0.2
                reasons.append("SMA20 < SMA50 (bearish)")
        
        # RSI
        if analysis["rsi"]:
            if analysis["rsi"] < 30:
                signals.append(1)
                confidence += 0.25
                reasons.append(f"RSI={analysis['rsi']:.1f} (oversold)")
            elif analysis["rsi"] > 70:
                signals.append(-1)
                confidence += 0.25
                reasons.append(f"RSI={analysis['rsi']:.1f} (overbought)")
            else:
                confidence += 0.1
                reasons.append(f"RSI={analysis['rsi']:.1f} (neutral)")
        
        # MACD
        if analysis["macd"] and analysis["macd_signal"]:
            if analysis["macd"] > analysis["macd_signal"]:
                signals.append(1)
                confidence += 0.2
                reasons.append("MACD > Signal (bullish)")
            else:
                signals.append(-1)
                confidence += 0.2
                reasons.append("MACD < Signal (bearish)")
        
        # Bollinger Bands
        if analysis["bb_lower"] and analysis["bb_upper"]:
            if analysis["price"] <= analysis["bb_lower"]:
                signals.append(1)
                confidence += 0.15
                reasons.append("Price <= BB Lower (oversold)")
            elif analysis["price"] >= analysis["bb_upper"]:
                signals.append(-1)
                confidence += 0.15
                reasons.append("Price >= BB Upper (overbought)")
        
        # Decyzja końcowa
        avg_signal = np.mean(signals) if signals else 0
        
        if avg_signal > 0.3:
            decision = "BUY"
        elif avg_signal < -0.3:
            decision = "SELL"
        else:
            decision = "HOLD"
            confidence = max(0.1, confidence * 0.5)
        
        result = {
            "signal": decision,
            "confidence": min(1.0, confidence),
            "reasons": reasons,
            "price": analysis["price"],
            "timestamp": datetime.now().isoformat()
        }
        
        # Zapisz decyzję
        self.last_decision = result
        self.decision_history.append(result)
        if len(self.decision_history) > 100:
            self.decision_history.pop(0)
        
        return result


class SentimentAnalyzer:
    """Moduł analizy sentymentu (placeholder dla LLM)"""
    
    def __init__(self):
        self.news_cache = []
        self.sentiment_score = 0.0
    
    def analyze_news(self, query="Bitcoin"):
        """Analiza sentymentu newsów (do implementacji z Twitter/RSS)"""
        # Placeholder — w przyszłości integracja z Twitter API / RSS
        return {"score": 0.0, "source": "neutral"}
    
    def get_aggregate_sentiment(self):
        """Zwróć zagregowany sentyment"""
        return self.sentiment_score


if __name__ == "__main__":
    brain = TradingBrain()
    print("=== Hermes Trading Brain ===")
    print(f"Para: {brain.pair}")
    print(f"Timeframe: {brain.timeframe}")
    print(f"Max position: {brain.max_position_pct*100}%")
    print(f"Stop-loss: {brain.stop_loss_pct*100}%")
    print(f"Take-profit: {brain.take_profit_pct*100}%")
