from decimal import Decimal
from unittest import mock

from django.test import TestCase

from accounts.models import User
from catalog.models import Category, Product
from core.models import BusinessSettings


def make_user(email="a@example.com", **kw):
    kw.setdefault("first_name", "Ada")
    kw.setdefault("last_name", "Obi")
    kw.setdefault("phone", "08012345678")
    return User.objects.create_user(email=email, password="Str0ng-pass!", **kw)


def make_product(name="Blender", price="10000", stock=10, **kw):
    cat = kw.pop("category", None) or Category.objects.get_or_create(name="Kitchen")[0]
    if kw.get("previous_price") is not None:
        kw["previous_price"] = Decimal(str(kw["previous_price"]))
    return Product.objects.create(name=name, price=Decimal(price), stock=stock, category=cat, **kw)


CHECKOUT = {
    "full_name": "Ada Obi", "email": "a@example.com", "phone": "08012345678",
    "address": "1 Allen Avenue", "state": "Lagos", "city": "Ikeja", "notes": "",
}


def paystack_ok(reference, amount_naira, **extra):
    data = {"status": "success", "id": 99, "reference": reference, "amount": int(Decimal(amount_naira) * 100),
            "currency": "NGN", "channel": "card", "gateway_response": "Successful"}
    data.update(extra)
    return data


class StoreTestCase(TestCase):
    def setUp(self):
        # Django's TestCase never commits, so transaction.on_commit callbacks (how the app queues emails)
        # would never fire. Run them immediately so tests can inspect mail.outbox.
        patcher = mock.patch("django.db.transaction.on_commit", side_effect=lambda func, *a, **k: func())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.biz = BusinessSettings.load()
        self.biz.referral_enabled = True
        self.biz.referral_reward_amount = Decimal("1500")
        self.biz.default_delivery_fee = Decimal("0")
        self.biz.save()
        self.user = make_user()
        self.product = make_product()

    def login(self, user=None):
        self.client.force_login(user or self.user)

    def place_order(self, user=None, use_wallet=False, only=None):
        """Create an order through the real service and start payment with a mocked Paystack."""
        from orders import services as order_services

        order = order_services.create_order_from_cart(
            user or self.user, {**CHECKOUT, "email": (user or self.user).email}, use_wallet=use_wallet,
            only_product_id=only,
        )
        return order

    def pay(self, order):
        """Simulate a successful, verified Paystack payment for the order."""
        from payments import services as pay_services
        from payments.models import PaymentTransaction

        with mock.patch("payments.paystack.initialize_transaction",
                        return_value={"authorization_url": "https://paystack.test/x", "access_code": "ac"}):
            pay_services.start_payment(order, "http://testserver/payments/callback/")
        txn = PaymentTransaction.objects.filter(order=order).latest("id")
        with mock.patch("payments.paystack.verify_transaction",
                        return_value=paystack_ok(txn.reference, txn.amount)):
            pay_services.verify_and_process(txn.reference)
        order.refresh_from_db()
        txn.refresh_from_db()
        return order, txn
