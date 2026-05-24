#!/usr/bin/env python3
"""
Hermes Task Bridge - MCP Server
Pozwala agentowi Hermes odebrać zadania od innych agentów
i wykonać je lokalnie bez zużywania tokenów API.
"""
import os
import json
import subprocess
import logging
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfiguracja
WORKSPACE = Path("/home/r00t/hermes-trading")
LOG_FILE = WORKSPACE / "logs" / "task_bridge.log"

server = Server("hermes-task-bridge")

@server.list_tools()
async def list_tools():
    """Lista dostępnych narzędzi"""
    return [
        Tool(
            name="execute_task",
            description="Wykonaj zadanie w workspace Hermes-Trading. "
                        "Dostępne zadania: update_file, run_script, git_commit, "
                        "run_tests, scan_models, update_config",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "enum": ["update_file", "run_script", "git_commit", 
                                 "run_tests", "scan_models", "update_config",
                                 "read_file", "list_files", "run_command"],
                        "description": "Typ zadania do wykonania"
                    },
                    "params": {
                        "type": "object",
                        "description": "Parametry zadania (zależne od typu)"
                    }
                },
                "required": ["task"]
            }
        ),
        Tool(
            name="get_status",
            description="Pobierz status projektu Hermes-Trading",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="delegate_to_agent",
            description="Deleguj zadanie do konkretnego agenta (analyst, risk, executor)",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent": {
                        "type": "string",
                        "enum": ["analyst", "risk", "executor", "orchestrator"],
                        "description": "Agent do którego delegujemy"
                    },
                    "task": {
                        "type": "string",
                        "description": "Opis zadania"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "default": "medium"
                    }
                },
                "required": ["agent", "task"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Wykonaj narzędzie"""
    
    if name == "execute_task":
        task = arguments.get("task")
        params = arguments.get("params", {})
        return await execute_task(task, params)
    
    elif name == "get_status":
        return await get_status()
    
    elif name == "delegate_to_agent":
        agent = arguments.get("agent")
        task = arguments.get("task")
        priority = arguments.get("priority", "medium")
        return await delegate_to_agent(agent, task, priority)
    
    return [TextContent(type="text", text=f"Nieznane narzędzie: {name}")]


async def execute_task(task: str, params: dict):
    """Wykonaj zadanie"""
    try:
        if task == "update_file":
            file_path = params.get("file")
            content = params.get("content")
            if file_path and content:
                full_path = WORKSPACE / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
                return [TextContent(type="text", text=f"Zaktualizowano: {file_path}")]
            return [TextContent(type="text", text="Brak parametru file/content")]
        
        elif task == "git_commit":
            message = params.get("message", "Auto update")
            result = subprocess.run(
                ["git", "-C", str(WORKSPACE), "add", "-A"],
                capture_output=True, text=True
            )
            result = subprocess.run(
                ["git", "-C", str(WORKSPACE), "commit", "-m", message],
                capture_output=True, text=True
            )
            return [TextContent(type="text", text=f"Git commit: {result.stdout}")]
        
        elif task == "scan_models":
            result = subprocess.run(
                ["/home/r00t/trading-env/bin/python3", 
                 str(WORKSPACE / "src/brain/daily_model_scanner.py"), "scan"],
                capture_output=True, text=True, timeout=120
            )
            return [TextContent(type="text", text=f"Model scan: {result.stdout[-500:]}")]
        
        elif task == "run_command":
            cmd = params.get("command")
            if cmd:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=60,
                    cwd=str(WORKSPACE)
                )
                return [TextContent(type="text", text=f"Exit: {result.returncode}\n{result.stdout}")]
            return [TextContent(type="text", text="Brak parametru command")]
        
        else:
            return [TextContent(type="text", text=f"Nieznane zadanie: {task}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Błąd: {str(e)}")]


async def get_status():
    """Pobierz status"""
    try:
        # Git status
        result = subprocess.run(
            ["git", "-C", str(WORKSPACE), "log", "--oneline", "-5"],
            capture_output=True, text=True
        )
        git_log = result.stdout.strip()
        
        # PM2 status
        result = subprocess.run(
            ["pm2", "list"],
            capture_output=True, text=True
        )
        pm2_status = result.stdout.strip()
        
        # Model registry
        registry_path = WORKSPACE / "config/model_registry.json"
        if registry_path.exists():
            registry = json.loads(registry_path.read_text())
            model_count = registry.get("total_models", 0)
        else:
            model_count = 0
        
        status = f"""=== Hermes-Trading Status ===
Git:
{git_log}

PM2:
{pm2_status}

Models: {model_count}
"""
        return [TextContent(type="text", text=status)]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Błąd: {str(e)}")]


async def delegate_to_agent(agent: str, task: str, priority: str):
    """Deleguj zadanie do agenta"""
    # Zapisz zadanie do kolejki
    task_queue = WORKSPACE / "config" / "task_queue.json"
    
    tasks = []
    if task_queue.exists():
        tasks = json.loads(task_queue.read_text())
    
    task_entry = {
        "id": len(tasks) + 1,
        "agent": agent,
        "task": task,
        "priority": priority,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    tasks.append(task_entry)
    task_queue.write_text(json.dumps(tasks, indent=2))
    
    return [TextContent(type="text", text=f"Zadanie #{task_entry['id']} delegowane do {agent}: {task}")]


if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    
    asyncio.run(main())
