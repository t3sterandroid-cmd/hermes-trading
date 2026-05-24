#!/usr/bin/env python3
"""
Hermes Trading System - Smart Model Router v2.1
Z API Guard - automatyczna ochrona przed płatnymi wywołaniami
"""
import os
import json
import logging
import time
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("/home/r00t/hermes-trading/config/.env")
logger = logging.getLogger(__name__)

# === API GUARD IMPORT ===
from src.brain.api_guard import api_guard

# === TASK DEFINITIONS ===
TASK_CONFIG = {
    "coding": {
        "description": "Pisanie kodu, refactoring, debugowanie",
        "preferred_providers": ["groq", "or", "nvidia"],
        "preferred_models": [
            "groq/compound-mini",
            "qwen/qwen3-coder:free",
            "openai/gpt-oss-120b:free",
            "deepseek-ai/deepseek-v4-flash",
        ],
        "min_context": 32768,
        "needs_tools": True,
        "speed_priority": True,
    },
    "analysis": {
        "description": "Analiza danych, raporty, research",
        "preferred_providers": ["groq", "or", "nvidia"],
        "preferred_models": [
            "llama-3.3-70b-versatile",
            "deepseek/deepseek-v4-flash:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
        ],
        "min_context": 65536,
        "needs_tools": True,
        "speed_priority": False,
    },
    "reasoning": {
        "description": "Złożone decyzje, planowanie, strategia",
        "preferred_providers": ["or", "nvidia", "groq"],
        "preferred_models": [
            "deepseek/deepseek-v4-flash:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "llama-3.3-70b-versatile",
        ],
        "min_context": 131072,
        "needs_tools": True,
        "speed_priority": False,
    },
    "light": {
        "description": "Proste zadania, odpowiedzi, formatowanie",
        "preferred_providers": ["groq", "or", "nvidia"],
        "preferred_models": [
            "llama-3.1-8b-instant",
            "groq/compound-mini",
            "openai/gpt-oss-20b:free",
        ],
        "min_context": 8192,
        "needs_tools": False,
        "speed_priority": True,
    },
    "sentiment": {
        "description": "Analiza sentymentu, newsów, social media",
        "preferred_providers": ["groq", "or"],
        "preferred_models": [
            "llama-3.3-70b-versatile",
            "google/gemma-4-31b-it:free",
        ],
        "min_context": 32768,
        "needs_tools": False,
        "speed_priority": True,
    },
    "trading": {
        "description": "Decyzje tradingowe, sygnały, ryzyko",
        "preferred_providers": ["or", "nvidia", "groq"],
        "preferred_models": [
            "deepseek/deepseek-v4-flash:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "llama-3.3-70b-versatile",
        ],
        "min_context": 65536,
        "needs_tools": True,
        "speed_priority": False,
    },
}

# === PROVIDER HEALTH TRACKING ===
PROVIDER_STATS = {
    "or": {"requests": 0, "errors": 0, "total_time": 0, "last_error": None, "disabled_until": None},
    "groq": {"requests": 0, "errors": 0, "total_time": 0, "last_error": None, "disabled_until": None},
    "nvidia": {"requests": 0, "errors": 0, "total_time": 0, "last_error": None, "disabled_until": None},
}


def load_model_registry():
    """Załaduj rejestr modeli z pliku"""
    registry_path = Path("/home/r00t/hermes-trading/config/model_registry.json")
    if registry_path.exists():
        with open(registry_path) as f:
            return json.load(f)
    return {"providers": {}, "total_models": 0}


def get_available_models(provider_id, registry):
    """Pobierz listę dostępnych modeli dla providera"""
    provider_names = {"or": "OpenRouter", "groq": "Groq", "nvidia": "NVIDIA"}
    pname = provider_names.get(provider_id, provider_id)
    pdata = registry.get("providers", {}).get(pname, {})
    return pdata.get("models", [])


def is_provider_healthy(provider_id):
    """Sprawdź czy provider jest zdrowy"""
    stats = PROVIDER_STATS.get(provider_id, {})
    disabled_until = stats.get("disabled_until")
    
    if disabled_until:
        if datetime.now().timestamp() < disabled_until:
            return False
        else:
            stats["disabled_until"] = None
            stats["errors"] = 0
    
    if stats.get("errors", 0) >= 5:
        stats["disabled_until"] = datetime.now().timestamp() + 300
        logger.warning(f"Provider {provider_id} wyłączony na 5 minut (5 błędów)")
        return False
    
    return True


def select_model_for_task(task_type, registry=None):
    """Wybierz optymalny model dla zadania"""
    if registry is None:
        registry = load_model_registry()
    
    task = TASK_CONFIG.get(task_type, TASK_CONFIG["reasoning"])
    
    for model_id in task["preferred_models"]:
        for provider_id in task["preferred_providers"]:
            if not is_provider_healthy(provider_id):
                continue
            
            models = get_available_models(provider_id, registry)
            for m in models:
                if m["id"] == model_id:
                    if m["ctx"] >= task["min_context"]:
                        if not task["needs_tools"] or m.get("tools", False):
                            return {
                                "model": model_id,
                                "provider": provider_id,
                                "ctx": m["ctx"],
                                "tools": m.get("tools", False),
                            }
    
    # Fallback
    for provider_id in ["groq", "or", "nvidia"]:
        if not is_provider_healthy(provider_id):
            continue
        models = get_available_models(provider_id, registry)
        for m in models:
            return {"model": m["id"], "provider": provider_id, "ctx": m["ctx"], "tools": m.get("tools", False)}
    
    logger.error("Brak dostępnych modeli!")
    return None


def call_model(model_info, messages, max_tokens=1024, tools=None):
    """Wywołaj model z ochroną API Guard"""
    provider = model_info["provider"]
    model = model_info["model"]
    
    # === API Guard Check ===
    endpoint_map = {
        "or": "/v1/chat/completions",
        "groq": "/openai/v1/chat/completions",
        "nvidia": "/v1/chat/completions",
    }
    endpoint = endpoint_map.get(provider, "/v1/chat/completions")
    
    if not api_guard.check_call(provider, endpoint, model):
        raise PermissionError(f"ZABLOKOWANE: Próba płatnego wywołania {provider}/{model}")
    
    start_time = time.time()
    
    try:
        if provider == "or":
            result = _call_openrouter(model, messages, max_tokens, tools)
        elif provider == "groq":
            result = _call_groq(model, messages, max_tokens)
        elif provider == "nvidia":
            result = _call_nvidia(model, messages, max_tokens)
        else:
            raise ValueError(f"Nieznany provider: {provider}")
        
        elapsed = time.time() - start_time
        record_api_result(provider, True, elapsed)
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        record_api_result(provider, False, elapsed)
        raise


def _call_openrouter(model, messages, max_tokens, tools=None):
    """Wywołaj OpenRouter API"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
        "Content-Type": "application/json",
    }
    body = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]


def _call_groq(model, messages, max_tokens):
    """Wywołaj Groq API"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY', '')}",
        "Content-Type": "application/json",
    }
    body = {"model": model, "messages": messages, "max_tokens": max_tokens}
    
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]


def _call_nvidia(model, messages, max_tokens):
    """Wywołaj NVIDIA API"""
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('NVIDIA_API_KEY', '')}",
        "Content-Type": "application/json",
    }
    body = {"model": model, "messages": messages, "max_tokens": max_tokens}
    
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]


def record_api_result(provider, success, elapsed):
    """Zapisz wynik wywołania API"""
    PROVIDER_STATS[provider]["requests"] += 1
    PROVIDER_STATS[provider]["total_time"] += elapsed
    if success:
        PROVIDER_STATS[provider]["errors"] = 0
    else:
        PROVIDER_STATS[provider]["errors"] += 1
        PROVIDER_STATS[provider]["last_error"] = datetime.now().isoformat()


def ask(task_type, prompt, max_tokens=1024, tools=None):
    """Wygodna funkcja: zadaj pytanie z automatycznym wyborem modelu"""
    registry = load_model_registry()
    model_info = select_model_for_task(task_type, registry)
    
    if not model_info:
        raise RuntimeError("Brak dostępnych modeli!")
    
    messages = [{"role": "user", "content": prompt}]
    return call_model(model_info, messages, max_tokens, tools)


def get_model(task_type="reasoning"):
    """Pobierz info o modelu dla zadania"""
    registry = load_model_registry()
    return select_model_for_task(task_type, registry)


def get_provider_stats():
    """Pobierz statystyki providerów"""
    return {**PROVIDER_STATS, "api_guard": api_guard.get_stats()}
