"""
Vercel Entry Point.
Warum diese Datei: Vercel erkennt Python-Dateien im /api-Verzeichnis
als Serverless Functions. Diese Datei reexportiert die FastAPI-App
als 'app'-Variable – das ist der Konventionsname, den Vercel's
ASGI-Runtime erwartet.

Alle weiteren Konfigurationen bleiben in app/main_api.py gekapselt.
"""

# sys.path-Anpassung notwendig, da Vercel den Projektroot nicht
# automatisch zum Python-Path hinzufügt
import sys
from pathlib import Path

# Projektroot zum Suchpfad hinzufügen
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.main_api import app  # noqa: E402  (Import nach sys.path-Manipulation)

__all__ = ["app"]
