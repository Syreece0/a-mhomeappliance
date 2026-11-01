from celery import shared_task
from django.utils import timezone


@shared_task
def dispatch_due_campaigns():
    from .models import Campaign
    from .services import send_campaign

    sent = 0
    due = Campaign.objects.filter(status=Campaign.SCHEDULED, scheduled_for__lte=timezone.now())
    for campaign_id in list(due.values_list("pk", flat=True)):
        send_campaign(campaign_id)
        sent += 1
    return sent
