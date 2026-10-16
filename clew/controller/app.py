"""The controller: the only service with the Docker socket (handoff §15.3, §22). Internal only; the API is its
only caller, with CONTROLLER_TOKEN. It starts, kills and restarts Clew's own explorer containers, and restarts
Clew's services for S3. Nothing else.

Run: python -m clew.controller.app
"""

from __future__ import annotations

import os
import random
import secrets

import docker
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="clew-controller", docs_url=None, redoc_url=None, openapi_url=None)
LABEL = "clew.role"
PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", "clew")
PASS_ENV = [
    "FALKORDB_HOST",
    "FALKORDB_PORT",
    "FALKORDB_PASSWORD",
    "CLEW_GRAPH",
    "SHOP_URL",
    "SHOP_EXPLORER_PASSWORD",
    "LLM_BACKEND",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "GOOGLE_API_KEY",
    "CLEW_SCREENSHOTS",
]
RESTARTABLE = {"falkordb", "mcp", "api", "scheduler", "reporter", "strategist"}


def auth(authorization: str = Header("")) -> None:
    token = os.environ.get("CONTROLLER_TOKEN", "")
    if not token or not secrets.compare_digest(authorization.removeprefix("Bearer ").strip(), token):
        raise HTTPException(403)


def client() -> docker.DockerClient:
    return docker.from_env()


def explorers(c) -> list:
    return c.containers.list(filters={"label": f"{LABEL}=explorer"})


class Scale(BaseModel):
    n: int = Field(ge=0, le=8)
    session: str | None = None
    mode: str = "shared"


@app.post("/scale", dependencies=[Depends(auth)])
def scale(req: Scale) -> dict:
    """Run exactly n explorer containers (0 stops them all)."""
    c = client()
    running = explorers(c)
    if req.n == 0 or (req.session and any(x.labels.get("clew.session") != req.session for x in running)):
        for x in running:
            x.remove(force=True)
        running = []
    env = {k: os.environ[k] for k in PASS_ENV if k in os.environ}
    env.update({"CLEW_SESSION": req.session or "", "CLEW_MODE": req.mode})
    for _ in range(req.n - len(running)):
        c.containers.run(
            os.environ.get("EXPLORER_IMAGE", "clew-explorer"),
            detach=True,
            environment=env,
            network=os.environ.get("CLEW_NETWORK", f"{PROJECT}_default"),
            ipc_mode="host",
            init=True,
            restart_policy={"Name": "unless-stopped"},
            labels={LABEL: "explorer", "clew.session": req.session or ""},
            volumes={
                os.environ.get("SCREENSHOT_VOLUME", f"{PROJECT}_screenshots"): {
                    "bind": "/data/screenshots",
                    "mode": "rw",
                }
            },
        )
    for x in running[req.n :]:
        x.remove(force=True)
    return {"ok": True, "explorers": len(explorers(c))}


@app.post("/kill", dependencies=[Depends(auth)])
def kill() -> dict:
    """S2: SIGKILL one explorer mid-task. Its restart policy brings it back as a new agent."""
    running = explorers(client())
    if not running:
        return {"ok": False, "error": "no explorers running"}
    victim = random.choice(running)
    victim.kill()
    return {"ok": True, "killed": victim.name}


class Restart(BaseModel):
    services: list[str] = sorted(RESTARTABLE - {"api"})


@app.post("/restart", dependencies=[Depends(auth)])
def restart(req: Restart) -> dict:
    """S3: restart Clew's services (FalkorDB included); state survives in the graph (AOF)."""
    c = client()
    done = []
    for svc in req.services:
        if svc not in RESTARTABLE:
            continue
        for x in c.containers.list(
            filters={"label": [f"com.docker.compose.project={PROJECT}", f"com.docker.compose.service={svc}"]}
        ):
            x.restart(timeout=10)
            done.append(x.name)
    for x in explorers(c):
        x.restart(timeout=5)
        done.append(x.name)
    return {"ok": True, "restarted": done}


@app.get("/health")
def health() -> dict:
    return {"ok": True}


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("CONTROLLER_PORT", "8003")))


if __name__ == "__main__":
    main()
