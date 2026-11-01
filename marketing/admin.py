from django.contrib import admin

from .models import Campaign, NewsletterSubscriber, UnsubscribedEmail

admin.site.register(NewsletterSubscriber)
admin.site.register(UnsubscribedEmail)
admin.site.register(Campaign)
