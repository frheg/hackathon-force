"""Three sketches of an oil and gas app, served together: an index page links them.

    /copilot/   NCS Copilot: plain-language questions over Sodir's FactPages, answered with SQL
    /logs/      Log Lens: well logs, lithology predicted by a model trained on FORCE 2020, explained by the LLM
    /decline/   Field Pulse: field production, a decline-curve forecast against Sodir's reserves, a field brief
    /status/    every connection the pod has
"""

import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response

from common import HERE, page
from sketches import copilot, decline, logs, status

api = FastAPI(title="Hackathon sketches")
for sketch in (copilot, logs, decline, status):
    api.include_router(sketch.router)


@api.get("/", response_class=HTMLResponse)
def index():
    return page("index.html")


@api.get("/style.css")
def style():
    return Response((HERE / "pages" / "style.css").read_text(), media_type="text/css")


class Prefix:
    """The proxy passes the full path (/hackathon/...). Setting root_path makes the routes match without the prefix."""

    def __init__(self, app, prefix: str):
        self.app, self.prefix = app, prefix.rstrip("/")

    async def __call__(self, scope, receive, send):
        if self.prefix and scope["type"] in ("http", "websocket") and scope["path"].startswith(self.prefix):
            scope = dict(scope, root_path=self.prefix)
        await self.app(scope, receive, send)


app = Prefix(api, os.environ.get("ROOT_PATH", ""))
