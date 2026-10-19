from __future__ import annotations

from unittest.mock import patch

from ceo.notifier import notificar_telegram


def test_notifier_sin_env():
    with patch("ceo.notifier.os.environ.get", return_value=None):
        assert notificar_telegram("test") is False


def test_notifier_ok():
    class R:
        status_code = 200
    with patch("ceo.notifier.os.environ.get",
               side_effect=lambda k, d=None: "fake" if k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID") else d), \
         patch("ceo.notifier.requests.post", return_value=R()):
        assert notificar_telegram("test") is True


def test_notifier_fail_open():
    with patch("ceo.notifier.os.environ.get",
               side_effect=lambda k, d=None: "fake" if k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID") else d), \
         patch("ceo.notifier.requests.post", side_effect=Exception("boom")):
        assert notificar_telegram("test") is False
