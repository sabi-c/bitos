import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from integrations.contracts import AdapterResult, CalendarAdapter, EmailAdapter, MessageAdapter, TaskAdapter


class _MockAdapter:
    def create_task(self, title: str, details: str | None = None) -> AdapterResult:
        return AdapterResult(success=True, external_id="1")

    def complete_task(self, provider_task_id: str) -> AdapterResult:
        return AdapterResult(success=True)

    def send_message(self, recipient: str, body: str) -> AdapterResult:
        return AdapterResult(success=True)

    def send_email(self, recipient: str, subject: str, body: str) -> AdapterResult:
        return AdapterResult(success=True)

    def create_event(self, title: str, starts_at_iso: str, ends_at_iso: str) -> AdapterResult:
        return AdapterResult(success=True)


class AdapterContractTests(unittest.TestCase):
    def test_mock_adapter_satisfies_all_domain_protocols(self):
        adapter = _MockAdapter()
        self.assertIsInstance(adapter, TaskAdapter)
        self.assertIsInstance(adapter, MessageAdapter)
        self.assertIsInstance(adapter, EmailAdapter)
        self.assertIsInstance(adapter, CalendarAdapter)


if __name__ == "__main__":
    unittest.main()
