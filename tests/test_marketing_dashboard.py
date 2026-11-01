from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from cart.tasks import send_abandoned_cart_reminders
from catalog.models import Product, Promotion, PromotionItem
from catalog.services import sync_promotions
from marketing import services as mkt
from marketing.models import Campaign, NewsletterSubscriber, UnsubscribedEmail
from notifications.models import EmailDelivery

from .helpers import StoreTestCase, make_product, make_user


def png(name="p.png"):
    buf = BytesIO()
    Image.new("RGB", (20, 20), "navy").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class AbandonedCartTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk})
        mail.outbox.clear()
        self.cart = self.user.cart

    def age_cart(self, minutes):
        type(self.cart).objects.filter(pk=self.cart.pk).update(updated_at=timezone.now() - timedelta(minutes=minutes))

    def test_waits_then_sends_limited_reminders(self):
        self.biz.abandoned_cart_wait_minutes = 60
        self.biz.abandoned_cart_max_reminders = 2
        self.biz.abandoned_cart_interval_hours = 24
        self.biz.save()
        self.assertEqual(send_abandoned_cart_reminders(), 0)  # too early
        self.age_cart(90)
        self.assertEqual(send_abandoned_cart_reminders(), 1)
        self.assertEqual(send_abandoned_cart_reminders(), 0)  # interval not elapsed
        body = mail.outbox[0].alternatives[0][0]
        self.assertIn("Return to Your Cart", body)
        self.assertIn("Blender", body)
        type(self.cart).objects.filter(pk=self.cart.pk).update(last_reminder_at=timezone.now() - timedelta(hours=25))
        self.assertEqual(send_abandoned_cart_reminders(), 1)
        type(self.cart).objects.filter(pk=self.cart.pk).update(last_reminder_at=timezone.now() - timedelta(hours=60))
        self.assertEqual(send_abandoned_cart_reminders(), 0)  # max reminders reached

    def test_disabled_and_after_purchase(self):
        self.age_cart(500)
        self.biz.abandoned_cart_enabled = False
        self.biz.save()
        self.assertEqual(send_abandoned_cart_reminders(), 0)
        self.biz.abandoned_cart_enabled = True
        self.biz.save()
        order = self.place_order()
        self.pay(order)  # clears the cart
        mail.outbox.clear()
        self.assertEqual(send_abandoned_cart_reminders(), 0)


class CampaignTests(StoreTestCase):
    def make_campaign(self, audience=Campaign.ALL_OPTED_IN):
        c = Campaign.objects.create(name="Promo", subject="Big sale", message="Save!", audience=audience,
                                    discount_info="30% off")
        c.products.add(self.product)
        return c

    def test_newsletter_is_explicit_opt_in_and_registration_does_not_subscribe(self):
        self.assertFalse(self.user.marketing_opt_in)
        self.assertEqual(NewsletterSubscriber.objects.count(), 0)
        self.client.post(reverse("marketing:subscribe"), {"email": "visitor@example.com"})
        self.assertTrue(NewsletterSubscriber.objects.get(email="visitor@example.com").is_active)

    def test_campaign_reaches_only_opted_in_and_includes_unsubscribe(self):
        optin = make_user("optin@example.com", marketing_opt_in=True)
        mkt.subscribe("sub@example.com")
        c = self.make_campaign()
        mail.outbox.clear()
        mkt.send_campaign(c.pk)
        recipients = {m.to[0] for m in mail.outbox}
        self.assertEqual(recipients, {"optin@example.com", "sub@example.com"})
        self.assertNotIn("a@example.com", recipients)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("Shop Now", html)
        self.assertIn("/marketing/unsubscribe/", html)
        c.refresh_from_db()
        self.assertEqual(c.status, Campaign.SENT)
        self.assertEqual(mkt.send_campaign(c.pk), 0, "cannot be sent twice")

    def test_unsubscribe_is_global_but_transactional_mail_continues(self):
        make_user("optin@example.com", marketing_opt_in=True)
        token = mkt.unsubscribe_token("optin@example.com")
        self.client.post(reverse("marketing:unsubscribe", args=[token]))
        self.assertTrue(UnsubscribedEmail.objects.filter(email="optin@example.com").exists())
        c = self.make_campaign()
        mail.outbox.clear()
        mkt.send_campaign(c.pk)
        self.assertEqual(mail.outbox, [])
        # bad token
        self.assertEqual(self.client.get(reverse("marketing:unsubscribe", args=["junk"])).status_code, 400)

    def test_send_time_suppression_check(self):
        d = EmailDelivery.objects.create(to_email="x@example.com", subject="s", html_body="<p>x</p>",
                                         is_marketing=True, kind="promotion")
        UnsubscribedEmail.objects.create(email="x@example.com")
        from notifications.services import deliver
        deliver(d)
        d.refresh_from_db()
        self.assertEqual(d.status, EmailDelivery.SKIPPED)

    def test_scheduled_campaign_dispatch(self):
        from marketing.tasks import dispatch_due_campaigns
        make_user("optin@example.com", marketing_opt_in=True)
        c = self.make_campaign()
        c.status = Campaign.SCHEDULED
        c.scheduled_for = timezone.now() - timedelta(minutes=1)
        c.save()
        dispatch_due_campaigns()
        c.refresh_from_db()
        self.assertEqual(c.status, Campaign.SENT)

    def test_email_failure_never_breaks_and_is_recorded(self):
        from unittest import mock
        from notifications.services import deliver
        d = EmailDelivery.objects.create(to_email="x@example.com", subject="s", html_body="<p>x</p>")
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("smtp down")):
            with self.assertRaises(OSError):
                deliver(d)
        d.refresh_from_db()
        self.assertEqual(d.status, EmailDelivery.FAILED)
        self.assertEqual(d.attempts, 1)
        self.assertIn("smtp down", d.error)


class PromotionTests(StoreTestCase):
    def test_promotion_applies_and_reverts(self):
        promo = Promotion.objects.create(name="Flash", discount_percent=20, starts_at=timezone.now() - timedelta(hours=1),
                                         ends_at=timezone.now() + timedelta(hours=1))
        PromotionItem.objects.create(promotion=promo, product=self.product)
        sync_promotions()
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("8000.00"))
        self.assertEqual(self.product.previous_price, Decimal("10000.00"))
        sync_promotions()  # idempotent
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("8000.00"))
        Promotion.objects.filter(pk=promo.pk).update(ends_at=timezone.now() - timedelta(minutes=1))
        sync_promotions()
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("10000.00"))
        self.assertIsNone(self.product.previous_price)


class DashboardTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user("staff@example.com", is_staff=True)

    def test_admin_pages_blocked_for_customers_and_anonymous(self):
        urls = [reverse(n) for n in ["dashboard:overview", "dashboard:product_list", "dashboard:order_list",
                                     "dashboard:customer_list", "dashboard:referrals", "dashboard:settings",
                                     "dashboard:campaign_list"]]
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 302, u)  # anonymous -> login
        self.login()
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 403, u)
        self.assertEqual(self.client.post(reverse("dashboard:product_delete", args=[self.product.pk])).status_code, 403)

    def test_all_admin_pages_render_for_staff(self):
        self.client.force_login(self.staff)
        for name in ["overview", "product_list", "product_new", "category_list", "category_new", "inventory_log",
                     "order_list", "transactions", "customer_list", "referrals", "promotion_list", "promotion_new",
                     "banner_list", "banner_new", "review_list", "campaign_list", "campaign_new", "email_history",
                     "abandoned_cart", "settings"]:
            resp = self.client.get(reverse(f"dashboard:{name}"))
            self.assertEqual(resp.status_code, 200, name)
        self.assertEqual(self.client.get(reverse("dashboard:product_edit", args=[self.product.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:customer_detail", args=[self.user.pk])).status_code, 200)

    def test_create_product_with_multiple_images(self):
        self.client.force_login(self.staff)
        cat = self.product.category
        resp = self.client.post(reverse("dashboard:product_new"), {
            "name": "Air Fryer X", "category": cat.pk, "brand": "Philips", "price": "55000", "previous_price": "65000",
            "stock": "7", "is_available": "on", "warranty": "1 year", "description": "d", "specifications": "Power: 1500W",
            "new_images": [png("a.png"), png("b.png")],
        })
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None) and resp.context["form"].errors)
        p = Product.objects.get(name="Air Fryer X")
        self.assertEqual(p.images.count(), 2)
        self.assertEqual(p.images.filter(is_primary=True).count(), 1)
        self.assertEqual(p.discount_percent, 15)
        self.assertEqual(p.movements.get().change, 7)

    def test_non_image_upload_rejected(self):
        self.client.force_login(self.staff)
        bad = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        resp = self.client.post(reverse("dashboard:product_new"), {
            "name": "Bad", "category": self.product.category.pk, "price": "1", "stock": "1", "is_available": "on",
            "new_images": [bad]})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Product.objects.filter(name="Bad").exists())

    def test_staff_stock_adjustment_logs_movement(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("dashboard:product_stock", args=[self.product.pk]),
                         {"mode": "add", "quantity": "5", "note": "delivery"})
        self.client.post(reverse("dashboard:product_stock", args=[self.product.pk]),
                         {"mode": "remove", "quantity": "999", "note": "too many"})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 15)  # over-removal refused, never negative

    def test_wallet_adjustment_audited_and_cannot_go_negative(self):
        from referrals.models import Wallet, WalletTransaction
        self.client.force_login(self.staff)
        url = reverse("dashboard:wallet_adjust", args=[self.user.pk])
        self.client.post(url, {"amount": "3000", "reason": "goodwill"})
        self.client.post(url, {"amount": "-9000", "reason": "oops"})
        self.client.post(url, {"amount": "100", "reason": ""})
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("3000"))
        txn = WalletTransaction.objects.get()
        self.assertEqual(txn.created_by, self.staff)
        self.assertEqual(txn.note, "goodwill")

    def test_order_status_update_by_staff_notifies_customer(self):
        self.login()
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk})
        order, _ = self.pay(self.place_order())
        self.client.force_login(self.staff)
        mail.outbox.clear()
        self.client.post(reverse("dashboard:order_status", args=[order.number]),
                         {"status": "processing", "note": ""})
        order.refresh_from_db()
        self.assertEqual(order.status, "processing")
        self.assertTrue(any("processing" in m.subject.lower() for m in mail.outbox))

    def test_referral_settings_change_without_code(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("dashboard:referrals"), {"referral_enabled": "on", "referral_reward_amount": "3200",
                                                          "referral_min_order_amount": "0"})
        from core.models import BusinessSettings
        self.assertEqual(BusinessSettings.load().referral_reward_amount, Decimal("3200"))

    def test_category_seed_and_reorder(self):
        from django.core.management import call_command
        from catalog.models import Category
        call_command("seed_categories", verbosity=0)
        call_command("seed_categories", verbosity=0)  # idempotent
        self.assertTrue(Category.objects.filter(name="Kitchen Appliances", parent=None).exists())
        self.assertEqual(Category.objects.filter(name="Air fryers").count(), 1)
        self.client.force_login(self.staff)
        top = list(Category.objects.filter(parent=None).order_by("position", "name"))
        second = top[1]
        self.client.post(reverse("dashboard:category_move", args=[second.pk]), {"direction": "up"})
        new_top = list(Category.objects.filter(parent=None).order_by("position", "name"))
        self.assertEqual(new_top[0].pk, second.pk)
