from citypulse.worker import celery_app


def test_system_ping_task_is_registered_and_deterministic() -> None:
    result = celery_app.tasks["citypulse.system.ping"].apply()

    assert result.successful()
    assert result.get() == {"service": "citypulse-worker", "status": "ok"}
