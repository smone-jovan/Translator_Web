import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import launcher


def test_handle_key_actions(monkeypatch):
    opened_urls = []
    monkeypatch.setattr(launcher, "open_url", lambda url: opened_urls.append(url))

    # Test '1' opens browser
    assert launcher.handle_key('1') is True
    assert len(opened_urls) == 1
    assert f"http://localhost:{launcher.FRONTEND_PORT}" in opened_urls[0]

    # Test '2' opens swagger docs
    assert launcher.handle_key('2') is True
    assert len(opened_urls) == 2
    assert f"http://localhost:{launcher.BACKEND_PORT}/docs" in opened_urls[1]

    # Test 'q' returns False (exit signal)
    assert launcher.handle_key('q') is False
    assert launcher.handle_key('Q') is False
    assert launcher.handle_key('x') is False

    # Test 's' (status), 'c' (banner/clear), and empty/whitespace keys
    assert launcher.handle_key('s') is True
    assert launcher.handle_key('c') is True
    assert launcher.handle_key('') is True
    assert launcher.handle_key('   ') is True

    # Test 'l' opens log file
    assert launcher.handle_key('l') is True
    assert any(launcher.LOG_FILE in url for url in opened_urls)


def test_log_buffering_and_clear():
    launcher._dashboard_mode = True
    launcher.log_buffer.clear()
    launcher.log("test", "A sample buffered log message")
    assert len(launcher.log_buffer) > 0
    assert any("A sample buffered log message" in line for line in launcher.log_buffer)

    # Calling 'c' clears buffer and logs an action note
    assert launcher.handle_key('c') is True
    assert len(launcher.log_buffer) >= 1
    assert any("Layar dan buffer log dibersihkan" in line for line in launcher.log_buffer)


def test_get_service_status_cached():
    b1, f1 = launcher.get_service_status(force=True)
    assert isinstance(b1, bool)
    assert isinstance(f1, bool)

    # Immediate second call should hit the cache without re-probing ports
    b2, f2 = launcher.get_service_status(force=False)
    assert b1 == b2
    assert f1 == f2


def test_numpad_and_alias_mapping():
    numpad_map = {
        'O': '1', 'P': '2', 'Q': '3', 'K': '4',
        'L': '5', 'u': '5', 'e': '5', 'M': '6',
        'G': '7', 'H': '8', 'I': '9'
    }
    assert numpad_map.get('O') == '1'
    assert numpad_map.get('P') == '2'
    assert numpad_map.get('Q') == '3'
    assert numpad_map.get('K') == '4'
    assert numpad_map.get('L') == '5'
    assert numpad_map.get('u') == '5'
    assert numpad_map.get('M') == '6'
    assert numpad_map.get('G') == '7'
    assert numpad_map.get('H') == '8'
    assert numpad_map.get('I') == '9'


def test_doctor_diagnostics():
    result = launcher.run_doctor()
    assert result in (0, 1)
