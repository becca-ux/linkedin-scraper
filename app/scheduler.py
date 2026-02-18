"""APScheduler-based scheduling for automated scoring runs."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

# Stores scheduled job configs: [{list_id, role_key, example_cvs}]
_scheduled_jobs: list[dict] = []


def schedule_scoring_run(
    app,
    list_id: str,
    role_key: str,
    schedule: str = "daily",
    example_cvs: str | None = None,
):
    """Schedule a recurring scoring run.

    Args:
        app: Flask app instance (needed for app context).
        list_id: Amplemarket list ID.
        role_key: Role to score against.
        schedule: "daily" or "weekly".
        example_cvs: Optional example CVs for calibration.
    """
    from app.pipeline import run_scoring_pipeline

    def job():
        with app.app_context():
            try:
                run_scoring_pipeline(
                    amplemarket_api_key=app.config["AMPLEMARKET_API_KEY"],
                    anthropic_api_key=app.config["ANTHROPIC_API_KEY"],
                    list_id=list_id,
                    role_key=role_key,
                    example_cvs=example_cvs,
                )
            except Exception:
                logger.exception("Scheduled scoring run failed")

    job_id = f"score_{role_key}_{list_id}"

    if schedule == "weekly":
        scheduler.add_job(job, "cron", day_of_week="mon", hour=8, id=job_id, replace_existing=True)
    else:
        scheduler.add_job(job, "cron", hour=8, id=job_id, replace_existing=True)

    _scheduled_jobs.append(
        {"list_id": list_id, "role_key": role_key, "schedule": schedule}
    )
    logger.info("Scheduled %s scoring for list %s (%s)", role_key, list_id, schedule)


def schedule_auto_sourcing(
    app,
    role_key: str,
    schedule: str = "daily",
    city: str = "London",
    num_results: int = 10,
):
    """Schedule a recurring auto-sourcing run.

    Args:
        app: Flask app instance.
        role_key: Role to source for.
        schedule: "daily", "weekly", or "once" for immediate execution.
        city: City for LinkedIn search.
        num_results: Results per query.
    """
    from app.pipeline import run_auto_sourcing_pipeline

    def job():
        with app.app_context():
            try:
                run_auto_sourcing_pipeline(
                    serper_api_key=app.config["SERPER_API_KEY"],
                    anthropic_api_key=app.config["ANTHROPIC_API_KEY"],
                    role_key=role_key,
                    city=city,
                    num_results=num_results,
                )
            except Exception:
                logger.exception("Scheduled auto-sourcing run failed")

    job_id = f"auto_source_{role_key}"

    if schedule == "once":
        scheduler.add_job(job, "date", id=job_id, replace_existing=True)
    elif schedule == "weekly":
        scheduler.add_job(
            job, "cron", day_of_week="mon", hour=8, id=job_id, replace_existing=True
        )
    else:
        scheduler.add_job(job, "cron", hour=8, id=job_id, replace_existing=True)

    _scheduled_jobs.append(
        {"type": "auto_source", "role_key": role_key, "schedule": schedule}
    )
    logger.info("Scheduled auto-sourcing for %s (%s)", role_key, schedule)


def start_scheduler():
    """Start the background scheduler."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """Shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
