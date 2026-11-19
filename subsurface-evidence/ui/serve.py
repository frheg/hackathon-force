"""UI server: static files plus /api proxy to the backend (BACKEND_URL). Separate pod from the backend; stdlib + httpx only."""
import os
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8300")
app = FastAPI(docs_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=2000)  # the proxied JSON and the static files travel compressed to the browser


@app.api_route("/api/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy(path: str, req: Request):
    async with httpx.AsyncClient(timeout=1800) as c:
        r = await c.request(req.method, f"{BACKEND}/api/{path}", params=req.query_params, content=await req.body(), headers={"content-type": req.headers.get("content-type", "application/json")} if req.method == "POST" else None)
    return Response(r.content, r.status_code, media_type=r.headers.get("content-type"))


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8301")))
