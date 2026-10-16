"""Observers on a Playwright page: uncaught errors, console errors, 5xx responses and crashes (handoff §12.1)."""

from __future__ import annotations

from urllib.parse import urlsplit

from clew.oracles.detectors import Event


class Observer:
    def __init__(self, page, origin: str):
        self.events: list[Event] = []
        self.origin = urlsplit(origin).netloc
        page.on("pageerror", lambda e: self.events.append(Event("pageerror", f"{e.name}: {e.message}")))
        page.on("console", self._console)
        page.on("response", self._response)
        page.on("crash", lambda _p: self.events.append(Event("crash", "page crashed")))

    def _same_origin(self, url: str) -> bool:
        return urlsplit(url).netloc == self.origin

    def _console(self, msg) -> None:
        if msg.type == "error":
            self.events.append(Event("console_error", msg.text))

    def _response(self, resp) -> None:
        if resp.status >= 500 and self._same_origin(resp.url):
            self.events.append(
                Event("http_5xx", f"HTTP {resp.status}", url=resp.url, method=resp.request.method, status=resp.status)
            )

    def reset(self) -> None:
        self.events = []

    def take(self) -> list[Event]:
        out, self.events = self.events, []
        return out
