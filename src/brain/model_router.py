#!/usr/bin/env python3
"""
Hermes Trading System - Smart Model Routing
Automatyczny wybier modelu w zależności od zadania i obciążenia
"""
import os
import json
import logging
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("/home/r00t/hermes-trading/config/.env")
logger = logging.getLogger(__name__)

# === KONFIGURACJA MODELÓW ===
# Format: { "id": "nazwa_modelu", "provider": "openrouter|groq|nvidia|gemini", "context": int, "tools": bool, "speed": "fast|medium|slow", "task": ["reasoning","coding","analysis","light"] }

MODELS = {
    "or": {
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            {"id": "deepseek/deepseek-v4-flash:free", "ctx": 1048576, "tools": True, "speed": "medium", "task": ["reasoning", "analysis"]},
            {"id": "qwen/qwen3-coder:free", "ctx": 1048576, "tools": True, "speed": "medium", "task": ["coding"]},
            {"id": "nvidia/nemotron-3-super-120b-a12b:free", "ctx": 1000000, "tools": True, "speed": "slow", "task": ["reasoning", "analysis"]},
            {"id": "google/gemma-4-31b-it:free", "ctx": 262144, "tools": True, "speed": "medium", "task": ["analysis"]},
            {"id": "openai/gpt-oss-120b:free", "ctx": 131072, "tools": True, "speed": "medium", "task": ["reasoning", "coding"]},
        ]
    },
    "groq": {
        "api_key": os.getenv("GROQ_API_KEY", ""),
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            {"id": "llama-3.3-70b-versatile", "ctx": 131072, "tools": True, "speed": "fast", "task": ["reasoning", "analysis"]},
            {"id": "openai/gpt-oss-120b", "ctx": 131072, "tools": False, "speed": "fast", "task": ["reasoning"]},
            {"id": "llama-3.1-8b-instant", "ctx": 131072, "tools": True, "speed": "fast", "task": ["light"]},
            {"id": "qwen/qwen3-32b", "ctx": 131072, "tools": True, "speed": "fast", "task": ["reasoning", "analysis"]},
            {"id": "groq/compound-mini", "ctx": 131072, "tools": True, "speed": "fast", "task": ["light", "coding"]},
        ]
    },
    "nvidia": {
        "api_key": os.getenv("NVIDIA_API_KEY", ""),
        "base_url": "https://integrate.api.nvidia.com/v1",
        "models": [
            {"id": "meta/llama-3.3-70b-instruct", "ctx": 131072, "tools": True, "speed": "medium", "task": ["reasoning", "analysis"]},
            {"id": "deepseek-ai/deepseek-v4-flash", "ctx": 131072, "tools": True, "speed": "medium", "task": ["reasoning", "coding"]},
            {"id": "qwen/qwen3-coder-480b-a35b-instruct", "ctx": 131072, "tools": True, "speed": "medium", "task": ["coding"]},
        ]
    }
}

# === TASK-TO-MODEL MAPPING ===
TASK_MODEL_MAP = {
    "coding": ["groq/compound-mini", "qwen/qwen3-coder:free", "openai/gpt-oss-120b:free"],
    "analysis": ["llama-3.3-70b-versatile", "deepseek/deepseek-v4-flash:free", "nvidia/nemotron-3-super-120b-a12b:free"],
    "reasoning": ["deepseek/deepseek-v4-flash:free", "nvidia/nemotron-3-super-120b-a12b:free", "llama-3.3-70b-versatile"],
    "light": ["llama-3.1-8b-instant", "groq/compound-mini", "openai/gpt-oss-20b:free"],
}


class SmartModelRouter:
    """Inteligentny router modeli AI"""
    
    def __init__(self):
        self.MODELS = MODELS
        self.TASK_MODEL_MAP = TASK_MODEL_MAP
        self.stats = {p: {"requests": 0, "errors": 0, "total_time": 0} for p in MODELS}
    
    def get_model_for_task(self, task_type="reasoning", prefer_speed=False):
        """Wybierz najlepszy model dla danego zadania"""
        candidates = self.TASK_MODEL_MAP.get(task_type, self.TASK_MODEL_MAP["reasoning"])
        
        # Sortuj prędkość jeśli preferowana
        if prefer_speed:
            candidates = sorted(candidates, key=lambda m: next(
                (x["speed"] for p in self.MODELS for x in self.MODELS[p]["models"] if x["id"] == m), "medium"
            ))
        
        # Znajdź pierwszy działający model
        for model_id in candidates:
            for provider, config in self.MODELS.items():
                for m in config["models"]:
                    if m["id"] == model_id:
                        errors = self.stats[provider]["errors"]
                        if errors < 3:  # Max 3 błędy na provider
                            return {
                                "model": model_id,
                                "provider": provider,
                                "config": config,
                                "ctx": m["ctx"],
                                "tools": m["tools"],
                            }
        
        # Fallback na pierwszy dostępny
        for provider, config in self.MODELS.items():
            for m in config["models"]:
                return {
                    "model": m["id"],
                    "provider": provider,
                    "config": config,
                    "ctx": m["ctx"],
                    "tools": m["tools"],
                }
        
        return None
    
    def record_result(self, provider, success, elapsed):
        """Zapisz statystykę użycia"""
        self.stats[provider]["requests"] += 1
        if not success:
            self.stats[provider]["errors"] += 1
        self.stats[provider]["total_time"] += elapsed
    
    def get_stats(self):
        """Pobierz statystyki użycia"""
        return self.stats


# === GLOBAL ROUTER INSTANCE ===
router = SmartModelRouter()


def get_model(task_type="reasoning", prefer_speed=False):
    """Pomocnicza funkcja do pobrania modelu"""
    return router.get_model_for_task(task_type, prefer_speed)


if __name__ == "__main__":
    print("=== Hermes Smart Model Router ===\n")
    
    for task in ["coding", "analysis", "reasoning", "light"]:
        model = get_model(task)
        if model:
            print(f"{task:12s} → {model['model']} ({model['provider']})")
    
    print("\n=== Dostępne modele ===")
    for provider, config in MODELS.items():
        print(f"\n{provider}:")
        for m in config["models"]:
            print(f"  {m['id']:50s} ctx={m['ctx']:>10} tools={m['tools']} speed={m['speed']}")
