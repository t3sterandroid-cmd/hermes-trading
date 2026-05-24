#!/usr/bin/env python3
"""
Hermes Task Bridge - GitHub Issues Agent
Komunikacja przez GitHub Issues - zero tokenów API
"""
import os
import json
import subprocess
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WORKSPACE = Path("/home/r00t/hermes-trading")
QUEUE_FILE = WORKSPACE / "config" / "task_queue.json"


def create_task_issue(title, body, labels=None):
    """Utwórz issue z zadaniem"""
    cmd = [
        "gh", "issue", "create",
        "--repo", "t3sterandroid-cmd/hermes-trading",
        "--title", title,
        "--body", body,
    ]
    if labels:
        for label in labels:
            cmd.extend(["--label", label])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()


def list_pending_issues():
    """Pobierz otwarte issues"""
    result = subprocess.run(
        ["gh", "issue", "list", "--repo", "t3sterandroid-cmd/hermes-trading", 
         "--state", "open", "--json", "number,title,labels,body"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return json.loads(result.stdout)
    return []


def close_issue(issue_number, comment=None):
    """Zamknij issue po wykonaniu"""
    if comment:
        subprocess.run(
            ["gh", "issue", "comment", str(issue_number),
             "--repo", "t3sterandroid-cmd/hermes-trading",
             "--body", comment],
            capture_output=True, text=True
        )
    
    result = subprocess.run(
        ["gh", "issue", "close", str(issue_number),
         "--repo", "t3sterandroid-cmd/hermes-trading"],
        capture_output=True, text=True
    )
    return result.returncode == 0


def process_tasks():
    """Przetwórz zadania z issues"""
    issues = list_pending_issues()
    
    for issue in issues:
        title = issue.get("title", "")
        body = issue.get("body", "")
        number = issue.get("number")
        labels = [l["name"] for l in issue.get("labels", [])]
        
        logger.info(f"Przetwarzanie zadania #{number}: {title}")
        
        # Wykonaj zadanie na podstawie tytułu/labels
        result = execute_task_from_issue(title, body, labels)
        
        # Zamknij issue z wynikiem
        close_issue(number, f"Wykonano:\n{result}")
        
        logger.info(f"Zadanie #{number} zakończone")


def execute_task_from_issue(title, body, labels):
    """Wykonaj zadanie na podstawie issue"""
    title_lower = title.lower()
    
    if "update" in title_lower and "model" in title_lower:
        return run_model_scan()
    elif "git" in title_lower and "update" in title_lower:
        return run_git_update(body)
    elif "test" in title_lower:
        return run_tests()
    elif "file" in title_lower:
        return update_file_from_body(body)
    else:
        return f"Nie rozpoznano zadania: {title}"


def run_model_scan():
    """Uruchom skanowanie modeli"""
    result = subprocess.run(
        ["/home/r00t/trading-env/bin/python3",
         str(WORKSPACE / "src/brain/daily_model_scanner.py"), "scan"],
        capture_output=True, text=True, timeout=120
    )
    return result.stdout[-500:] if result.returncode == 0 else result.stderr


def run_git_update(message=None):
    """Wykonaj git update"""
    subprocess.run(["git", "-C", str(WORKSPACE), "add", "-A"], capture_output=True)
    msg = message or f"Auto update {datetime.now().isoformat()}"
    result = subprocess.run(
        ["git", "-C", str(WORKSPACE), "commit", "-m", msg],
        capture_output=True, text=True
    )
    return result.stdout


def run_tests():
    """Uruchom testy"""
    result = subprocess.run(
        ["python3", "-m", "pytest", str(WORKSPACE / "tests"), "-v"],
        capture_output=True, text=True, timeout=60
    )
    return result.stdout[-500:]


def update_file_from_body(body):
    """Zaktualizuj plik na podstawie treści issue"""
    # Parsuj body issue (format: path: filepath\ncontent: ...)
    lines = body.split("\n")
    file_path = None
    content_lines = []
    in_content = False
    
    for line in lines:
        if line.startswith("path:"):
            file_path = line.replace("path:", "").strip()
        elif line.startswith("content:"):
            in_content = True
        elif in_content:
            content_lines.append(line)
    
    if file_path and content_lines:
        full_path = WORKSPACE / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text("\n".join(content_lines))
        return f"Zaktualizowano: {file_path}"
    
    return "Nie udało się sparsować zadania"


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "process":
            process_tasks()
        elif sys.argv[1] == "list":
            issues = list_pending_issues()
            for i in issues:
                print(f"#{i['number']}: {i['title']}")
    else:
        print("Użycie: python task_bridge.py process|list")
