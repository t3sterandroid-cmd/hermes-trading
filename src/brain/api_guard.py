#!/usr/bin/env python3
"""
Hermes Trading System - API Guard
Blokuje płatne wywołania API, chroni przed przypadkowymi zakupami
"""
import os
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from functools import wraps

logger = logging.getLogger(__name__)

# === KONFIGURACJA OCHRONY ===

# Endpointy które są ZAWSZE dozwolone (darmowe)
ALLOWED_ENDPOINTS = {
    "or": [
        "/v1/chat/completions",
        "/v1/models",
    ],
    "groq": [
        "/openai/v1/chat/completions",
        "/openai/v1/models",
    ],
    "nvidia": [
        "/v1/chat/completions",
        "/v1/models",
    ],
    "gemini": [
        "/v1beta/models",
        "/v1beta/models/.*:generateContent",
    ],
}

# Endpointy które są ZABLOKOWANE (płatne/zakupy)
BLOCKED_PATTERNS = {
    "or": [
        r"/v1/pay",
        r"/v1/billing",
        r"/v1/credits",
        r"/v1/subscription",
        r"/v1/checkout",
        r"/v1/purchase",
        r"/v1/orders",
        r"/v1/payment",
    ],
    "groq": [
        r"/billing",
        r"/subscription",
        r"/credits",
        r"/purchase",
        r"/payment",
        r"/checkout",
        r"/orders",
    ],
    "nvidia": [
        r"/billing",
        r"/subscription",
        r"/credits",
        r"/purchase",
        r"/payment",
        r"/checkout",
    ],
    "gemini": [
        r"/billing",
        r"/subscription",
        r"/purchase",
        r"/payment",
    ],
}

# Modele które są ZABLOKOWANE (płatne)
BLOCKED_MODELS = {
    "or": [
        # Wszystkie modele bez :free są płatne
        # Router automatycznie wybiera tylko :free modele
    ],
    "groq": [
        # Groq ma darmowy tier, ale niektóre modele mogą być płatne
    ],
    "nvidia": [
        # NVIDIA ma darmowy tier
    ],
}


def is_endpoint_allowed(provider, endpoint):
    """Sprawdź czy endpoint jest dozwolony"""
    # Sprawdź czy endpoint jest na liście dozwolonych
    allowed = ALLOWED_ENDPOINTS.get(provider, [])
    for pattern in allowed:
        if re.match(pattern, endpoint) or endpoint == pattern:
            return True
    
    # Sprawdź czy endpoint nie jest zablokowany
    blocked = BLOCKED_PATTERNS.get(provider, [])
    for pattern in blocked:
        if re.search(pattern, endpoint):
            logger.warning(f"ZABLOKOWANY endpoint: {provider}{endpoint}")
            return False
    
    # Domyślnie blokuj nieznane endpointy
    logger.warning(f"Nieznany endpoint: {provider}{endpoint} - BLOKOWANY")
    return False


def is_model_allowed(provider, model_id):
    """Sprawdź czy model jest dozwolony (darmowy)"""
    # OpenRouter: tylko modele z :free
    if provider == "or":
        if ":free" not in model_id:
            logger.warning(f"ZABLOKOWANY model (płatny): {model_id}")
            return False
    
    # Sprawdź listę zablokowanych modeli
    blocked = BLOCKED_MODELS.get(provider, [])
    if model_id in blocked:
        logger.warning(f"ZABLOKOWANY model: {model_id}")
        return False
    
    return True


def guard_api_call(func):
    """Dekorator który chroni przed płatnymi wywołaniami API"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Wyciągnij provider i endpoint z argumentów
        provider = kwargs.get("provider", args[0] if args else None)
        endpoint = kwargs.get("endpoint", args[1] if len(args) > 1 else None)
        model = kwargs.get("model", args[2] if len(args) > 2 else None)
        
        # Sprawdź endpoint
        if endpoint and not is_endpoint_allowed(provider, endpoint):
            raise PermissionError(
                f"ZABLOKOWANE: Próba wywołania płatnego endpointu {provider}{endpoint}. "
                f"Agent nie może dokonywać zakupów."
            )
        
        # Sprawdź model
        if model and not is_model_allowed(provider, model):
            raise PermissionError(
                f"ZABLOKOWANE: Próba użycia płatnego modelu {model}. "
                f"Agent może używać tylko darmowych modeli."
            )
        
        return func(*args, **kwargs)
    
    return wrapper


class APIGuard:
    """Główna klasa ochrony API"""
    
    def __init__(self):
        self.blocked_calls = []
        self.allowed_calls = []
    
    def check_call(self, provider, endpoint, model=None):
        """Sprawdź czy wywołanie API jest dozwolone"""
        allowed = True
        reason = ""
        
        # Sprawdź endpoint
        if not is_endpoint_allowed(provider, endpoint):
            allowed = False
            reason = f"Zablokowany endpoint: {endpoint}"
        
        # Sprawdź model
        if model and not is_model_allowed(provider, model):
            allowed = False
            reason = f"Zablokowany model: {model}"
        
        # Zapisz w logach
        call_info = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "endpoint": endpoint,
            "model": model,
            "allowed": allowed,
            "reason": reason,
        }
        
        if allowed:
            self.allowed_calls.append(call_info)
        else:
            self.blocked_calls.append(call_info)
            logger.warning(f"ZABLOKOWANE WYWOŁANIE: {provider}{endpoint} - {reason}")
        
        return allowed
    
    def get_stats(self):
        """Pobierz statystyki"""
        return {
            "allowed_calls": len(self.allowed_calls),
            "blocked_calls": len(self.blocked_calls),
            "recent_blocked": self.blocked_calls[-5:] if self.blocked_calls else [],
        }


# === GLOBAL INSTANCE ===
api_guard = APIGuard()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    print("=== API Guard Test ===\n")
    
    # Test 1: Dozwolony endpoint
    result = api_guard.check_call("or", "/v1/chat/completions", "deepseek/deepseek-v4-flash:free")
    print(f"Test 1 (dozwolony): {'OK' if result else 'BLOKOWANY'}")
    
    # Test 2: Zablokowany endpoint
    result = api_guard.check_call("or", "/v1/billing/credits")
    print(f"Test 2 (zablokowany endpoint): {'OK' if result else 'BLOKOWANY'}")
    
    # Test 3: Zablokowany model (płatny)
    result = api_guard.check_call("or", "/v1/chat/completions", "gpt-4o")
    print(f"Test 3 (zablokowany model): {'OK' if result else 'BLOKOWANY'}")
    
    # Test 4: Dozwolony model
    result = api_guard.check_call("groq", "/openai/v1/chat/completions", "llama-3.3-70b-versatile")
    print(f"Test 4 (dozwolony): {'OK' if result else 'BLOKOWANY'}")
    
    print(f"\n=== Stats ===")
    print(api_guard.get_stats())
