"""Parse analysis_id from Celery task id (orchestration uses task_id=str(analysis.id); inline uses prefixes)."""

from uuid import UUID


def parse_analysis_id_from_celery_task_id(celery_task_id: str) -> UUID:
    try:
        return UUID(celery_task_id)
    except ValueError:
        pass
    for prefix in ("inline-", "instant-"):
        if celery_task_id.startswith(prefix):
            return UUID(celery_task_id[len(prefix) :])
    raise ValueError(f"Cannot derive analysis_id from celery_task_id={celery_task_id!r}")
