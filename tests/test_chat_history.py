"""Tests for ChatHistoryPanel and repository.list_sessions."""
import time
import pytest
import pygame

from device.storage.repository import DeviceRepository


@pytest.fixture
def repo(tmp_path):
    db = str(tmp_path / "test.db")
    r = DeviceRepository(db)
    r.initialize()
    return r


class TestListSessions:
    def test_empty(self, repo):
        assert repo.list_sessions() == []

    def test_returns_sessions_with_messages(self, repo):
        sid = repo.create_session("Chat 1")
        repo.add_message(sid, "user", "hello")
        sessions = repo.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["id"] == sid
        assert sessions[0]["msg_count"] == 1

    def test_excludes_empty_sessions(self, repo):
        repo.create_session("Empty")
        sid2 = repo.create_session("Has msgs")
        repo.add_message(sid2, "user", "hi")
        sessions = repo.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["id"] == sid2

    def test_excludes_greeting_sessions(self, repo):
        repo.create_greeting_session("hello there")
        sid = repo.create_session("Real chat")
        repo.add_message(sid, "user", "hi")
        sessions = repo.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["title"] == "Real chat"

    def test_ordered_newest_first(self, repo):
        s1 = repo.create_session("Old")
        repo.add_message(s1, "user", "a")
        time.sleep(0.05)
        s2 = repo.create_session("New")
        repo.add_message(s2, "user", "b")
        sessions = repo.list_sessions()
        assert sessions[0]["id"] == s2
        assert sessions[1]["id"] == s1

    def test_limit_and_offset(self, repo):
        for i in range(5):
            sid = repo.create_session(f"Chat {i}")
            repo.add_message(sid, "user", f"msg {i}")
            time.sleep(0.02)
        all_sessions = repo.list_sessions(limit=3)
        assert len(all_sessions) == 3
        page2 = repo.list_sessions(limit=3, offset=3)
        assert len(page2) == 2


class TestChatHistoryPanel:
    def test_panel_loads_sessions(self, repo):
        pygame.init()
        try:
            from screens.panels.chat_history import ChatHistoryPanel

            sid = repo.create_session("Test")
            repo.add_message(sid, "user", "hello")

            opened = []
            panel = ChatHistoryPanel(
                repository=repo,
                on_open_session=lambda sid: opened.append(sid),
                on_back=lambda: None,
            )
            panel.on_enter()
            # Wait for background thread
            import threading
            for t in threading.enumerate():
                if t.daemon and t != threading.current_thread():
                    t.join(timeout=2)

            assert panel._state == "ready"
            assert len(panel._sessions) == 1

            # Double press opens session
            panel.handle_action("DOUBLE_PRESS")
            assert opened == [sid]
        finally:
            pygame.quit()

    def test_panel_back(self, repo):
        pygame.init()
        try:
            from screens.panels.chat_history import ChatHistoryPanel

            backed = []
            panel = ChatHistoryPanel(
                repository=repo,
                on_open_session=lambda sid: None,
                on_back=lambda: backed.append(True),
            )
            panel.handle_action("LONG_PRESS")
            assert backed == [True]
        finally:
            pygame.quit()
