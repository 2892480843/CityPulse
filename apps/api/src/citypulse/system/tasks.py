from celery import shared_task


@shared_task(name="citypulse.system.ping")
def ping() -> dict[str, str]:
    return {"service": "citypulse-worker", "status": "ok"}
