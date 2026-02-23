"""
Web-Server Starter: Startet die FastAPI-Applikation mit uvicorn.

Usage:
    python run_server.py
    python run_server.py --port 9000
    CHURN_LOG_LEVEL=DEBUG python run_server.py
"""

import argparse
import sys

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Churn Early Warning Web Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host (Standard: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (Standard: 8000)")
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
        log_level="warning",  # uvicorn-Logs reduziert, App-Logs via config.settings
    )


if __name__ == "__main__":
    sys.exit(main())
