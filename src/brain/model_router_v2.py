#!/usr/bin/env python3
"""
Hermes Trading System - Smart Model Router v2.0
Automatyczny wybór modelu i providera w zależności od zadania
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

# === TASK DEFINITIONS ===
# Każde zadanie ma przypisany priorytet modeli i providerów

TASK_CONFIG = {
    "coding": {
        "description": "Pisanie kodu, refactoring, debugowanie",
        "preferred_providers": ["groq", "or", "nvidia"],
        "preferred_models": [
            "groq/compound-mini",           # Szybki, dobry do kodu
            "qwen/qwen3-coder:free",        # Specjalizowany w kodowaniu
            "openai/gpt-oss-120b:free",     # OpenAI coding model
            "deepseek-ai/deepseek-v4-flash", # DeepSeek coding
        ],
        "min_context": 32768,
        "needs_tools": True,
        "speed_priority": True,
    },
    "analysis": {
        "description": "Analiza danych, raporty, research",
        "preferred_providers": ["groq", "or", "nvidia"],
        "preferred_models": [
            "llama-3.3-70b-versatile",      # Szybki, dobry do analizy
            "deepseek/deepseek-v4-flash:free", # Duży context
            "nvidia/nemotron-3-super-120b-a12b:free", # Największy context
        ],
        "min_context": 65536,
        "needs_tools": True,
        "speed_priority": False,
    },
    "reasoning": {
        "description": "Złożone decyzje, planowanie, strategia",
        "preferred_providers": ["or", "nvidia", "groq"],
        "preferred_models": [
            "deepseek/deepseek-v4-flash:free", # Najlepszy reasoning
            "nvidia/nemotron-3-super-120b-a12b:free", # Duży context
            "llama-3.3-70b-versatile",      # Szybki fallback
        ],
        "min_context": 131072,
        "needs_tools": True,
        "speed_priority": False,
    },
    "light": {
        "description": "Proste zadania, odpowiedzi, formatowanie",
        "preferred_providers": ["groq", "or", "nvidia"],
        "preferred_models": [
            "llama-3.1-8b-instant",         # Najszybszy
            "groq/compound-mini",           # Szybki
            "openai/gpt-oss-20b:free",      # Lekki
        ],
        "min_context": 8192,
        "needs_tools": False,
        "speed_priority": True,
    },
    "sentiment": {
        "description": "Analiza sentymentu, newsów, social media",
        "preferred_providers": ["groq", "or"],
        "preferred_models": [
            "llama-3.3-70b-versatile",      # Dobry do NLP
            "google/gemma-4-31b-it:free",   # Google NLP
        ],
        "min_context": 32768,
        "needs_tools": False,
        "speed_priority": True,
    },
    "trading": {
        "description": "Decyzje tradingowe, sygnały, ryzyko",
        "preferred_providers": ["or", "nvidia", "groq"],
        "preferred_models": [
            "deepseek/deepseek-v4-flash:free", # Najlepszy do decyzji
            "nvidia/nemotron-3-super-120b-a12b:free", # Duży context
            "llama-3.3-70b-versatile",      # Szybki fallback
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
            # Reset po czasie
            stats["disabled_until"] = None
            stats["errors"] = 0
    
    # Max 5 błędów z rzędu
    if stats.get("errors", 0) >= 5:
        # Wyłącz na 5 minut
        stats["disabled_until"] = datetime.now().timestamp() + 300
        logger.warning(f"Provider {provider_id} wyłączony na 5 minut (5 błędów)")
        return False
    
    return True


def select_model_for_task(task_type, registry=None):
    """Wybierz optymalny model dla zadania"""
    if registry is None:
        registry = load_model_registry()
    
    task = TASK_CONFIG.get(task_type, TASK_CONFIG["reasoning"])
    
    # 1. Spróbuj preferowane modele w kolejności
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
                                "speed": m.get("speed", "medium"),
                            }
    
    # 2. Fallback: pierwszy dostępny model z preferowanego providera
    for provider_id in task["preferred_providers"]:
        if not is_provider_healthy(provider_id):
            continue
        
        models = get_available_models(provider_id, registry)
        for m in models:
            if m["ctx"] >= task["min_context"]:
                if not task["needs_tools"] or m.get("tools", False):
                    return {
                        "model": m["id"],
                        "provider": provider_id,
                        "ctx": m["ctx"],
                        "tools": m.get("tools", False),
                        "speed": m.get("speed", "medium"),
                    }
    
    # 3. Ostatni fallback: jakikolwiek dostępny model
    for provider_id in ["groq", "or", "nvidia"]:
        if not is_provider_healthy(provider_id):
            continue
        models = get_available_models(provider_id, registry)
        if models:
            m = models[0]
            return {
                "model": m["id"],
                "provider": provider_id,
                "ctx": m["ctx"],
                "tools": m.get("tools", False),
                "speed": m.get("speed", "medium"),
            }
    
    logger.error("Brak dostępnych modeli!")
    return None


def record_api_result(provider_id, success, elapsed):
    """Zapisz wynik wywołania API"""
    stats = PROVIDER_STATS[provider_id]
    stats["requests"] += 1
    stats["total_time"] += elapsed
    
    if success:
        stats["errors"] = 0  # Reset błędów przy sukcesie
    else:
        stats["errors"] += 1
        stats["last_error"] = datetime.now().isoformat()


def call_model(model_info, messages, max_tokens=1024, tools=None):
    """Wywołaj model przez odpowiedniego providera"""
    provider = model_info["provider"]
    model = model_info["model"]
    
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
        logger.error(f"Błąd {provider}/{model}: {e}")
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


def get_provider_stats():
    """Pobierz statystyki providerów"""
    return PROVIDER_STATS


# === CONVENIENCE FUNCTIONS ===

def ask(task_type, prompt, max_tokens=1024, tools=None):
    """Wygodna funkcja: zadaj pytanie z automatycznym wyborem modelu"""
    registry = load_model_registry()
    model_info = select_model_for_task(task_type, registry)
    
    if not model_info:
        raise RuntimeError("Brak dostępnych modeli!")
    
    messages = [{"role": "user", "content": prompt}]
    return call_model(model_info, messages, max_tokens, tools)


def get_model(task_type="reasoning"):
    """Pobierz info o modelu dla zadania (kompatybilność z v1)"""
    registry = load_model_registry()
    return select_model_for_task(task_type, registry)


# === GLOBAL INSTANCE ===
router = type('obj', (object,), {
    'get_model': get_model,
    'ask': ask,
    'get_stats': get_provider_stats,
})()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("=== Smart Model Router v2.0 Test ===\n")
        
        for task in TASK_CONFIG:
            model = get_model(task)
            if model:
                print(f"{task:12s} -> {model['model']:50s} ({model['provider']})")
        
        print("\n=== Provider Stats ===")
        for pid, stats in PROVIDER_STATS.items():
            print(f"  {pid}: {stats['requests']} req, {stats['errors']} err")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "ask":
        task = sys.argv[2] if len(sys.argv) > 2 else "reasoning"
        prompt = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else "Hello, how are you?"
        
        print(f"Task: {task}")
        print(f"Prompt: {prompt}")
        
        response = ask(task, prompt)
        print(f"\nResponse: {response.get('content', response)}")
    
    else:
        print("Użycie:")
        print("  python model_router.py test")
        print("  python model_router.py ask <task> <prompt>")
