"""Notifier interface for budget alerts, with console and webhook implementations."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from cloudlens.models import BudgetAlert


class Notifier(ABC):
    """A sink that a `BudgetAlert` can be delivered to."""

    @abstractmethod
    def notify(self, alert: BudgetAlert) -> None:
        """Deliver a single budget alert."""


class ConsoleNotifier(Notifier):
    """Prints the alert to stdout. Always available, no configuration needed."""

    def notify(self, alert: BudgetAlert) -> None:
        print(
            f"[BUDGET ALERT] {alert.project} ({alert.month}): "
            f"${alert.spent:,.2f} / ${alert.limit:,.2f} "
            f"({alert.percent_used:.0f}%, crossed {alert.threshold_crossed}% threshold)"
        )


class WebhookNotifier(Notifier):
    """POSTs the alert as JSON to a configured webhook URL."""

    def __init__(self, webhook_url: str, timeout_seconds: float = 5.0):
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds

    def notify(self, alert: BudgetAlert) -> None:
        payload = json.dumps(alert.model_dump(mode="json")).encode("utf-8")
        request = urllib.request.Request(
            self.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response.read()
        except urllib.error.URLError as exc:
            print(f"[BUDGET ALERT] Failed to deliver webhook for {alert.project}: {exc}")
