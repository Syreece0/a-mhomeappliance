from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


@receiver(post_save, sender=User)
def on_user_created(sender, instance, created, **kwargs):
    if not created:
        return
    from notifications import events

    user_id = instance.pk
    transaction.on_commit(lambda: events.welcome(User.objects.get(pk=user_id)))
