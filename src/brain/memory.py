#!/usr/bin/env python3
"""
Hermes Trading System - Memory Layer
Rozszerzona pamięć agenta z semantycznym wyszukiwaniem
"""
import os
import json
import sqlite3
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("/home/r00t/hermes-trading/config/.env")
logger = logging.getLogger(__name__)

DB_PATH = "/home/r00t/hermes-trading/data/memory.db"


class MemoryLayer:
    """Warstwa pamięci dla agenta Hermes"""
    
    def __init__(self):
        self.db_path = DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Inicjalizuj bazę danych pamięci"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Tabela faktów
        cur.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                source TEXT,
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT
            )
        """)
        
        # Tabela relacji między faktami
        cur.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_id_1 TEXT NOT NULL,
                fact_id_2 TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (fact_id_1) REFERENCES facts(id),
                FOREIGN KEY (fact_id_2) REFERENCES facts(id)
            )
        """)
        
        # Tabela sesji (kontekst rozmów)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                summary TEXT,
                facts_extracted TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Tabela decyzji tradingowych
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trading_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision TEXT NOT NULL,
                reason TEXT,
                outcome TEXT,
                pnl REAL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Indeksy
        cur.execute("CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_facts_created ON facts(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation_type)")
        
        conn.commit()
        conn.close()
        logger.info("Memory layer zainicjalizowana")
    
    def add_fact(self, content, category="general", source=None, confidence=1.0):
        """Dodaj fakt do pamięci"""
        fact_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        now = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Sprawdź czy fakt już istnieje
        cur.execute("SELECT id FROM facts WHERE id = ?", (fact_id,))
        if cur.fetchone():
            # Aktualizuj istniejący
            cur.execute("""
                UPDATE facts SET 
                    content = ?, category = ?, source = ?, confidence = ?,
                    updated_at = ?, access_count = access_count + 1
                WHERE id = ?
            """, (content, category, source, confidence, now, fact_id))
        else:
            # Dodaj nowy
            cur.execute("""
                INSERT INTO facts (id, content, category, source, confidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (fact_id, content, category, source, confidence, now, now))
        
        conn.commit()
        conn.close()
        logger.info(f"Fakt dodany/zaktualizowany: {fact_id[:8]}... [{category}]")
        return fact_id
    
    def search_facts(self, query, category=None, limit=10):
        """Wyszukaj fakty w pamięci"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Proste wyszukiwanie tekstowe (w przyszłości można dodać embeddings)
        if category:
            cur.execute("""
                SELECT id, content, category, confidence, created_at, access_count
                FROM facts
                WHERE content LIKE ? AND category = ?
                ORDER BY confidence DESC, access_count DESC
                LIMIT ?
            """, (f"%{query}%", category, limit))
        else:
            cur.execute("""
                SELECT id, content, category, confidence, created_at, access_count
                FROM facts
                WHERE content LIKE ?
                ORDER BY confidence DESC, access_count DESC
                LIMIT ?
            """, (f"%{query}%", limit))
        
        results = []
        for row in cur.fetchall():
            results.append({
                "id": row[0],
                "content": row[1],
                "category": row[2],
                "confidence": row[3],
                "created_at": row[4],
                "access_count": row[5],
            })
        
        # Zaktualizuj last_accessed
        for r in results:
            cur.execute("UPDATE facts SET last_accessed = ? WHERE id = ?",
                       (datetime.now().isoformat(), r["id"]))
        
        conn.commit()
        conn.close()
        return results
    
    def add_relation(self, fact_id_1, fact_id_2, relation_type, confidence=1.0):
        """Dodaj relację między faktami"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO relations (fact_id_1, fact_id_2, relation_type, confidence, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (fact_id_1, fact_id_2, relation_type, confidence, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_related_facts(self, fact_id, relation_type=None):
        """Pobierz fakty powiązane z danym faktem"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        if relation_type:
            cur.execute("""
                SELECT f.*, r.relation_type, r.confidence as rel_confidence
                FROM facts f
                JOIN relations r ON (f.id = r.fact_id_2 OR f.id = r.fact_id_1)
                WHERE (r.fact_id_1 = ? OR r.fact_id_2 = ?) AND r.relation_type = ?
                ORDER BY r.confidence DESC
            """, (fact_id, fact_id, relation_type))
        else:
            cur.execute("""
                SELECT f.*, r.relation_type, r.confidence as rel_confidence
                FROM facts f
                JOIN relations r ON (f.id = r.fact_id_2 OR f.id = r.fact_id_1)
                WHERE r.fact_id_1 = ? OR r.fact_id_2 = ?
                ORDER BY r.confidence DESC
            """, (fact_id, fact_id))
        
        results = []
        for row in cur.fetchall():
            results.append({
                "id": row[0],
                "content": row[1],
                "category": row[2],
                "relation_type": row[8],
                "confidence": row[9],
            })
        
        conn.close()
        return results
    
    def record_decision(self, decision, reason=None):
        """Zapisz decyzję tradingową"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO trading_decisions (decision, reason, created_at)
            VALUES (?, ?, ?)
        """, (decision, reason, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        logger.info(f"Decyzja zapisana: {decision[:50]}")
    
    def update_decision_outcome(self, decision_id, outcome, pnl=None):
        """Zaktualizuj wynik decyzji"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE trading_decisions SET outcome = ?, pnl = ?
            WHERE id = ?
        """, (outcome, pnl, decision_id))
        
        conn.commit()
        conn.close()
    
    def get_stats(self):
        """Pobierz statystyki pamięci"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        stats = {}
        
        for table in ["facts", "relations", "sessions", "trading_decisions"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cur.fetchone()[0]
        
        # Kategorie faktów
        cur.execute("SELECT category, COUNT(*) FROM facts GROUP BY category")
        stats["categories"] = {row[0]: row[1] for row in cur.fetchall()}
        
        # Ostatnie decyzje
        cur.execute("""
            SELECT decision, outcome, pnl, created_at 
            FROM trading_decisions 
            ORDER BY created_at DESC LIMIT 5
        """)
        stats["recent_decisions"] = [
            {"decision": r[0], "outcome": r[1], "pnl": r[2], "date": r[3]}
            for r in cur.fetchall()
        ]
        
        conn.close()
        return stats
    
    def export_memory(self, filepath=None):
        """Eksportuj pamięć do pliku JSON"""
        if not filepath:
            filepath = f"/home/r00t/trading/reports/memory_export_{datetime.now().strftime('%Y%m%d')}.json"
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        export = {
            "exported_at": datetime.now().isoformat(),
            "facts": [],
            "relations": [],
            "trading_decisions": [],
        }
        
        for table in ["facts", "relations", "trading_decisions"]:
            cur.execute(f"SELECT * FROM {table}")
            rows = cur.fetchall()
            export[table] = [dict(row) for row in rows]
        
        conn.close()
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(export, f, indent=2)
        
        logger.info(f"Pamięć wyeksportowana: {filepath}")
        return filepath
    
    def cleanup_old_facts(self, days=30, min_confidence=0.3):
        """Usuń stare, nisko Pewne fakty"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM facts
            WHERE created_at < datetime('now', ?)
            AND confidence < ?
            AND access_count < 3
        """, (f"-{days} days", min_confidence))
        
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"Usunięto {deleted} starych faktów")
        
        return deleted


# === GLOBAL INSTANCE ===
memory = MemoryLayer()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "stats":
            stats = memory.get_stats()
            print(json.dumps(stats, indent=2))
        elif sys.argv[1] == "search" and len(sys.argv) > 2:
            results = memory.search_facts(" ".join(sys.argv[2:]))
            for r in results:
                print(f"[{r['category']}] {r['content'][:80]}...")
        elif sys.argv[1] == "export":
            path = memory.export_memory()
            print(f"Eksportowano: {path}")
    else:
        print("Użycie:")
        print("  python memory.py stats")
        print("  python memory.py search <query>")
        print("  python memory.py export")
