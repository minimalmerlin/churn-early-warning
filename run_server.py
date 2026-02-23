"""
Web-Server Starter: Startet die FastAPI-Applikation mit uvicorn.

Unterstützt die PORT-Umgebungsvariable für Railway, Render und andere
Cloud-Plattformen, die den Port zur Laufzeit injizieren.

Usage:
    python run_server.py                 # Lokal: http://127.0.0.1:8000
    python run_server.py --port 9000
    python run_server.py --host 0.0.0.0  # Docker / Cloud
    PORT=8080 python run_server.py       # Cloud-Plattform-Modus
    CHURN_LOG_LEVEL=DEBUG python run_server.py
"""

import argparse
import os
import sys

import uvicorn


def main() -> None:
    # PORT-Env-Variable: Railway, Render und Fly.io injizieren den Port so.
    # Warum os.getenv als Default: Plattform-Konvention vor CLI-Argument.
    env_port = int(os.getenv("PORT", "8000"))
    env_host = os.getenv("HOST", "127.0.0.1")

    parser = argparse.ArgumentParser(description="Churn Early Warning Web Server")
    parser.add_argument("--host", default=env_host, help="Host (Standard: $HOST oder 127.0.0.1)")
    parser.add_argument("--port", type=int, default=env_port, help="Port (Standard: $PORT oder 8000)")
    parser.add_argument("--reload", action="store_true", help="Auto-Reload bei Code-Änderungen")
    args = parser.parse_args()

    print(f"Server gestartet: http://{args.host}:{args.port}")
    print(f"API-Docs:         http://{args.host}:{args.port}/docs")
    print("Zum Beenden: CTRL+C")

    uvicorn.run(
        "app.main_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="warning",
    )


if __name__ == "__main__":
    sys.exit(main())
