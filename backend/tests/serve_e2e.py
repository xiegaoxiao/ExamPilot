"""Browser tests always get a NEW temporary workspace, never the user's demo data."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.database import Workspace
from backend.app.main import create_app
from backend.demo import initialize_demo
import uvicorn

if __name__ == "__main__":
    root = Path(tempfile.mkdtemp(prefix="exampilot-browser-"))
    initialize_demo(Workspace(root))
    print(f"Browser test workspace: {root}", flush=True)
    uvicorn.run(create_app(root), host="127.0.0.1", port=8001)
