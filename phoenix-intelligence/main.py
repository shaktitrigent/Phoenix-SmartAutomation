import sys

# When running as a PyInstaller bundle, sys._MEIPASS is the temp extraction dir.
# It must be on sys.path so that the `api` and `services` packages can be imported.
if getattr(sys, "frozen", False):
    sys.path.insert(0, sys._MEIPASS)

from api.server import app  # direct import — traceable by PyInstaller
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
