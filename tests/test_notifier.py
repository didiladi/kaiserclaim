"""Notifier, failure hook and reminder digest."""
import asyncio
from datetime import date
from unittest.mock import MagicMock, patch

from core.config import get_settings
from services.notifier import notify
from workers.tasks import NotifyOnFailure, _should_push_reminders, celery_app

_CFG = dict(ha_url="http://ha.test:8123", ha_token="tok", ha_notify_service="signal_x")


def _patched(**over):
    s = get_settings()
    return [patch.object(s, k, v) for k, v in {**_CFG, **over}.items()]


def _with(over, fn):
    ps = _patched(**over)
    for p in ps:
        p.start()
    try:
        return fn()
    finally:
        for p in ps:
            p.stop()


def test_notify_disabled_when_unconfigured_makes_no_request():
    with patch("urllib.request.urlopen") as op:
        for over in ({"ha_url": ""}, {"ha_token": "CHANGE_ME"}, {"ha_notify_service": ""}):
            assert _with(over, lambda: notify("hi")) is False
    op.assert_not_called()


def test_notify_posts_to_ha_notify_service():
    resp = MagicMock(status=200)
    resp.__enter__.return_value = resp
    with patch("urllib.request.urlopen", return_value=resp) as op:
        assert _with({}, lambda: notify("hello")) is True
    req = op.call_args.args[0]
    assert req.full_url == "http://ha.test:8123/api/services/notify/signal_x"
    assert req.get_header("Authorization") == "Bearer tok"
    assert b"hello" in req.data


def test_notify_never_raises():
    with patch("urllib.request.urlopen", side_effect=OSError("down")):
        assert _with({}, lambda: notify("x")) is False


def test_celery_tasks_use_failure_notifier():
    assert issubclass(celery_app.tasks["workers.tasks.submit_to_oegk"].__class__, NotifyOnFailure)


def test_on_failure_sends_short_message_without_details():
    task = celery_app.tasks["workers.tasks.submit_to_merkur"]
    with patch("services.notifier.notify") as n:
        task.on_failure(RuntimeError("secret detail"), "tid", ("11111111-1111-1111-1111-111111111111",), {}, None)
    msg = n.call_args.args[0]
    assert "submit_to_merkur" in msg and "RuntimeError" in msg
    assert "secret detail" not in msg


def test_reminder_push_policy():
    monday, tuesday = date(2026, 10, 5), date(2026, 10, 6)
    far = [("A", "p", 40)]
    near = [("A", "p", 5)]
    assert not _should_push_reminders([], monday)
    assert _should_push_reminders(far, monday)
    assert not _should_push_reminders(far, tuesday)
    assert _should_push_reminders(near, tuesday)
