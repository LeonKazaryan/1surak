import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

log = logging.getLogger(__name__)
# index.html is asked again on every visit, so a new build shows at once; the bundles it names have a content
# hash in their names, so they can be kept forever
FRESH = {"Cache-Control": "no-cache"}
FOREVER = {"Cache-Control": "public, max-age=31536000, immutable"}


def mount_spa(app: FastAPI, static_dir: Path) -> None:
    root = static_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        log.warning("UI build not found at %s, serving API only", root)
        return

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        try:
            candidate = (root / path).resolve()
            if candidate.is_file() and candidate.is_relative_to(root) and candidate != index:
                hashed = candidate.parent == root / "assets"
                return FileResponse(candidate, headers=FOREVER if hashed else FRESH)
        except (ValueError, OSError):
            pass
        return FileResponse(index, headers=FRESH)
