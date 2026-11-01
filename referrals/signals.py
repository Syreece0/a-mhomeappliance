from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_referral_code_and_wallet(sender, instance, created, **kwargs):
    """Every account gets a unique referral code (AM + user id) and an empty wallet."""
    if not created:
        return
    from .models import ReferralCode, Wallet

    ReferralCode.objects.get_or_create(user=instance, defaults={"code": f"AM{instance.pk:05d}"})
    Wallet.objects.get_or_create(user=instance)
