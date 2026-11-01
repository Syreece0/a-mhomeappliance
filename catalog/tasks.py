from celery import shared_task

from . import services


@shared_task
def sync_promotions():
    return services.sync_promotions()
