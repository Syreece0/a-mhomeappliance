from celery import shared_task

from . import services


@shared_task
def expire_unpaid_orders():
    return services.expire_unpaid_orders()
