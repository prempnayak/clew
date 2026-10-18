"""GitHub issues for our own repo only. GITHUB_FILING = on | dry_run | off.

dry_run (hosted judge sessions) numbers issues from a graph counter and keeps them in the UI only.

`python -m clew.reporter.github --create-labels` creates the labels in config/github.yaml.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass

import httpx

from clew.common.config import env, load


@dataclass
class Issue:
    number: int
    url: str


class GitHub:
    def __init__(self, mode: str | None = None, repo: str | None = None, token: str | None = None):
        self.mode = (mode or env("GITHUB_FILING", "dry_run")).lower()
        self.repo = repo or env("GITHUB_REPO")
        self.token = token or env("GITHUB_TOKEN")
        cfg = load("github")
        self.api = cfg.get("api", "https://api.github.com")
        self.max_per_hour = int(cfg.get("max_issues_per_hour", 20))
        self._created: list[float] = []

    @property
    def live(self) -> bool:
        return self.mode == "on" and bool(self.repo and self.token)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def create(self, title: str, body: str, labels: list[str], dry_number: int) -> Issue:
        if self.mode == "off":
            raise RuntimeError("GITHUB_FILING=off")
        if not self.live:
            return Issue(dry_number, f"dry-run://issues/{dry_number}")
        now = time.time()
        self._created = [t for t in self._created if now - t < 3600]
        if len(self._created) >= self.max_per_hour:
            raise RuntimeError("issue rate limit reached")
        r = httpx.post(
            f"{self.api}/repos/{self.repo}/issues",
            headers=self._headers(),
            timeout=20,
            json={"title": title, "body": body, "labels": labels},
        )
        r.raise_for_status()
        self._created.append(now)
        data = r.json()
        return Issue(data["number"], data["html_url"])

    def comment(self, number: int, body: str) -> None:
        if not self.live:
            return
        r = httpx.post(
            f"{self.api}/repos/{self.repo}/issues/{number}/comments",
            headers=self._headers(),
            timeout=20,
            json={"body": body},
        )
        r.raise_for_status()

    def close(self, number: int) -> None:
        if not self.live:
            return
        r = httpx.patch(
            f"{self.api}/repos/{self.repo}/issues/{number}",
            headers=self._headers(),
            timeout=20,
            json={"state": "closed", "state_reason": "completed"},
        )
        r.raise_for_status()

    def create_labels(self) -> None:
        for label in load("github")["labels"]:
            r = httpx.post(f"{self.api}/repos/{self.repo}/labels", headers=self._headers(), timeout=20, json=label)
            if r.status_code not in (201, 422):  # 422: already exists
                r.raise_for_status()
            print(label["name"], r.status_code)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--create-labels", action="store_true")
    args = p.parse_args()
    if args.create_labels:
        GitHub(mode="on").create_labels()
