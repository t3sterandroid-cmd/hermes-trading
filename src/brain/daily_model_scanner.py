#!/usr/bin/env python3
"""
Hermes Skill: Daily Model Scanner
Codziennie skanuje dostępne modele na wszystkich providerach
i aktualizuje konfigurację Smart Model Router
"""
import os
import json
import logging
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("/home/r00t/hermes-trading/config/.env")
logger = logging.getLogger(__name__)

CONFIG_DIR = Path("/home/r00t/hermes-trading/config")
MODEL_REGISTRY = CONFIG_DIR / "model_registry.json"
ROUTER_CONFIG = Path("/home/r00t/hermes-trading/src/brain/model_router.py")


class ModelScanner:
    """Skanuje dostępne modele na wszystkich providerach"""
    
    def __init__(self):
        self.providers = {
            "or": {
                "name": "OpenRouter",
                "api_key": os.getenv("OPENROUTER_API_KEY", ""),
                "url": "https://openrouter.ai/api/v1/models",
                "headers": {"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}"},
                "filter": lambda m: ":free" in m.get("id", ""),
                "extract": lambda m: {
                    "id": m["id"],
                    "ctx": m.get("context_length", 0),
                    "tools": "tools" in m.get("supported_parameters", []),
                    "speed": self._estimate_speed(m),
                    "task": self._detect_tasks(m),
                }
            },
            "groq": {
                "name": "Groq",
                "api_key": os.getenv("GROQ_API_KEY", ""),
                "url": "https://api.groq.com/openai/v1/models",
                "headers": {"Authorization": f"Bearer {os.getenv('GROQ_API_KEY', '')}"},
                "filter": lambda m: True,  # Wszystkie modele Groq są darmowe
                "extract": lambda m: {
                    "id": m["id"],
                    "ctx": m.get("context_length", 131072),
                    "tools": True,
                    "speed": "fast",  # Groq jest zawsze szybki
                    "task": self._detect_tasks(m),
                }
            },
            "nvidia": {
                "name": "NVIDIA",
                "api_key": os.getenv("NVIDIA_API_KEY", ""),
                "url": "https://integrate.api.nvidia.com/v1/models",
                "headers": {"Authorization": f"Bearer {os.getenv('NVIDIA_API_KEY', '')}"},
                "filter": lambda m: True,
                "extract": lambda m: {
                    "id": m["id"],
                    "ctx": m.get("context_length", 131072),
                    "tools": True,
                    "speed": "medium",
                    "task": self._detect_tasks(m),
                }
            }
        }
        self.discovered = {}
    
    def _estimate_speed(self, model):
        """Oszacuj prędkość modelu na podstawie rozmiaru"""
        ctx = model.get("context_length", 0)
        if ctx > 500000:
            return "slow"
        elif ctx > 100000:
            return "medium"
        return "fast"
    
    def _detect_tasks(self, model):
        """Wykryj typy zadań na podstawie nazwy modelu"""
        name = model.get("id", "").lower()
        tasks = []
        
        if any(kw in name for kw in ["coder", "code", "programming"]):
            tasks.append("coding")
        if any(kw in name for kw in ["reason", "think", "logic"]):
            tasks.append("reasoning")
        if any(kw in name for kw in ["instruct", "chat", "it-"]):
            tasks.append("analysis")
        if any(kw in name for kw in ["instant", "fast", "lite", "mini", "small", "8b"]):
            tasks.append("light")
        
        if not tasks:
            tasks = ["reasoning", "analysis"]
        
        return tasks
    
    def scan_provider(self, provider_id):
        """Skanuj modele jednego providera"""
        config = self.providers.get(provider_id)
        if not config or not config["api_key"]:
            logger.warning(f"Brak API key dla {provider_id}")
            return []
        
        try:
            resp = requests.get(config["url"], headers=config["headers"], timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            models = data.get("data", [])
            filtered = []
            
            for m in models:
                if config["filter"](m):
                    try:
                        extracted = config["extract"](m)
                        filtered.append(extracted)
                    except Exception as e:
                        logger.error(f"Błąd ekstrakcji modelu {m.get('id')}: {e}")
            
            logger.info(f"{config['name']}: Znaleziono {len(filtered)} modeli")
            return filtered
            
        except Exception as e:
            logger.error(f"Błąd skanowania {provider_id}: {e}")
            return []
    
    def scan_all(self):
        """Skanuj wszystkich providerów"""
        logger.info("=== Rozpoczęcie skanowania modeli ===")
        
        for provider_id in self.providers:
            models = self.scan_provider(provider_id)
            self.discovered[provider_id] = models
        
        total = sum(len(m) for m in self.discovered.values())
        logger.info(f"=== Skanowanie zakończone: {total} modeli ===")
        return self.discovered
    
    def save_registry(self):
        """Zapisz rejestr modeli"""
        registry = {
            "timestamp": datetime.now().isoformat(),
            "total_models": sum(len(m) for m in self.discovered.values()),
            "providers": {}
        }
        
        for provider_id, models in self.discovered.items():
            provider_name = self.providers[provider_id]["name"]
            registry["providers"][provider_name] = {
                "count": len(models),
                "models": models
            }
        
        with open(MODEL_REGISTRY, "w") as f:
            json.dump(registry, f, indent=2)
        
        logger.info(f"Rejestr zapisany: {MODEL_REGISTRY}")
        return registry
    
    def update_router_config(self):
        """Zaktualizuj konfigurację routera na podstawie wyników"""
        if not self.discovered:
            logger.warning("Brak wyników skanowania")
            return False
        
        # Generuj nowy kod routera
        router_code = self._generate_router_code()
        
        with open(ROUTER_CONFIG, "w") as f:
            f.write(router_code)
        
        logger.info(f"Router zaktualizowany: {ROUTER_CONFIG}")
        return True
    
    def _generate_router_code(self):
        """Generuj kod routera na podstawie wyników"""
        models_json = json.dumps(self.discovered, indent=4)
        
        return f'''#!/usr/bin/env python3
"""
Hermes Trading System - Smart Model Routing
AUTO-GENERATED by daily_model_scanner.py
Last updated: {datetime.now().isoformat()}
"""
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("/home/r00t/hermes-trading/config/.env")
logger = logging.getLogger(__name__)

# === AUTO-GENERATED MODEL REGISTRY ===
MODELS = {models_json}

# === TASK-TO-MODEL MAPPING ===
TASK_MODEL_MAP = {{
    "coding": ["groq/compound-mini", "qwen/qwen3-coder:free", "openai/gpt-oss-120b:free"],
    "analysis": ["llama-3.3-70b-versatile", "deepseek/deepseek-v4-flash:free", "nvidia/nemotron-3-super-120b-a12b:free"],
    "reasoning": ["deepseek/deepseek-v4-flash:free", "nvidia/nemotron-3-super-120b-a12b:free", "llama-3.3-70b-versatile"],
    "light": ["llama-3.1-8b-instant", "groq/compound-mini", "openai/gpt-oss-20b:free"],
}}


class SmartModelRouter:
    """Inteligentny router modeli AI"""
    
    def __init__(self):
        self.MODELS = MODELS
        self.TASK_MODEL_MAP = TASK_MODEL_MAP
        self.stats = {{p: {{"requests": 0, "errors": 0, "total_time": 0}} for p in MODELS}}
    
    def get_model_for_task(self, task_type="reasoning", prefer_speed=False):
        """Wybierz najlepszy model dla danego zadania"""
        candidates = self.TASK_MODEL_MAP.get(task_type, self.TASK_MODEL_MAP["reasoning"])
        
        for model_id in candidates:
            for provider, config in self.MODELS.items():
                for m in config:
                    if m["id"] == model_id:
                        errors = self.stats[provider]["errors"]
                        if errors < 3:
                            return {{
                                "model": model_id,
                                "provider": provider,
                                "config": config,
                                "ctx": m["ctx"],
                                "tools": m["tools"],
                            }}
        
        # Fallback
        for provider, config in self.MODELS.items():
            for m in config:
                return {{"model": m["id"], "provider": provider, "config": config, "ctx": m["ctx"], "tools": m["tools"]}}
        return None
    
    def record_result(self, provider, success, elapsed):
        self.stats[provider]["requests"] += 1
        if not success:
            self.stats[provider]["errors"] += 1
        self.stats[provider]["total_time"] += elapsed
    
    def get_stats(self):
        return self.stats


router = SmartModelRouter()


def get_model(task_type="reasoning", prefer_speed=False):
    return router.get_model_for_task(task_type, prefer_speed)
'''


def scan_and_update():
    """Główna funkcja: skanuj i aktualizuj"""
    scanner = ModelScanner()
    scanner.scan_all()
    scanner.save_registry()
    scanner.update_router_config()
    return scanner.discovered


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        results = scan_and_update()
        total = sum(len(m) for m in results.values())
        print(f"\\n=== Wynik: {total} modeli ===")
        for provider, models in results.items():
            print(f"  {provider}: {len(models)} modeli")
    else:
        print("Użycie: python daily_model_scanner.py scan")
