from celery import Celery
from celery.signals import after_setup_logger

from citypulse.shared.config import get_settings
from citypulse.shared.logging import configure_logging

settings = get_settings()
celery_app = Celery(
    "citypulse",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["citypulse.system.tasks"],
)
celery_app.conf.update(
    accept_content=["json"],
    enable_utc=True,
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_serializer="json",
    timezone="Asia/Shanghai",
    worker_prefetch_multiplier=1,
)
celery_app.autodiscover_tasks(["citypulse.system"], force=True)


@after_setup_logger.connect
def configure_job_process_logging(**_: object) -> None:
    configure_logging(settings.log_level, "citypulse-jobs")
