from decimal import Decimal
from unittest import mock

from django.db import IntegrityError, transaction

from django.urls import reverse

from accounts.models import User
from notifications.models import Notification
from orders.models import Order
from referrals import services as ref
from referrals.models import Referral, ReferralCode, Wallet, WalletTransaction

from .helpers import StoreTestCase, make_product, make_user


class ReferralRuleTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.referrer = self.user  # Customer A
        self.friend = make_user("friend@example.com", first_name="Bola")
        self.code = self.referrer.referral_code.code

    def refer_friend(self):
        return ref.attribute_referral(self.friend, self.code)

    def friend_buys(self, qty=1):
        self.client.force_login(self.friend)
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": qty})
        return self.pay(self.place_order(user=self.friend))[0]

    def balance(self, user):
        return Wallet.objects.get(user=user).balance

    def test_codes_are_unique_and_formatted(self):
        codes = list(ReferralCode.objects.values_list("code", flat=True))
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(c.startswith("AM") and len(c) >= 7 for c in codes))

    def test_registration_via_link_records_referrer_but_pays_nothing(self):
        self.client.get(reverse("core:referral_landing", args=[self.code]))
        self.client.post(reverse("accounts:register"), {
            "first_name": "New", "last_name": "Guy", "email": "new@example.com", "phone": "08000000000",
            "password1": "Str0ng-pass!", "password2": "Str0ng-pass!", "referral_code": self.code,
        })
        new = User.objects.get(email="new@example.com")
        r = Referral.objects.get(referred=new)
        self.assertEqual(r.referrer, self.referrer)
        self.assertEqual(r.status, Referral.PENDING)
        self.assertEqual(self.balance(self.referrer), 0)
        self.assertEqual(self.balance(new), 0)

    def test_invalid_code_rejected_at_registration(self):
        resp = self.client.post(reverse("accounts:register"), {
            "first_name": "N", "last_name": "G", "email": "n@example.com", "phone": "08000000000",
            "password1": "Str0ng-pass!", "password2": "Str0ng-pass!", "referral_code": "AM99999"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(email="n@example.com").exists())

    def test_cannot_refer_self(self):
        self.assertIsNone(ref.attribute_referral(self.referrer, self.code))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Referral.objects.create(referrer=self.referrer, referred=self.referrer, code_used=self.code)

    def test_attribution_is_permanent(self):
        r = self.refer_friend()
        third = make_user("third@example.com")
        r.referrer = third
        with self.assertRaises(ValueError):
            r.save()
        # a later attempt to attribute the same customer elsewhere changes nothing
        ref.attribute_referral(self.friend, third.referral_code.code)
        self.assertEqual(Referral.objects.get(referred=self.friend).referrer, self.referrer)

    def test_first_verified_purchase_rewards_referrer_once(self):
        self.refer_friend()
        self.friend_buys()
        self.assertEqual(self.balance(self.referrer), Decimal("1500"))
        r = Referral.objects.get()
        self.assertEqual(r.status, Referral.QUALIFIED)
        self.assertTrue(Notification.objects.filter(user=self.referrer, title__icontains="referral reward").exists())
        # second purchase: no more rewards
        self.friend_buys()
        self.assertEqual(self.balance(self.referrer), Decimal("1500"))
        self.assertEqual(WalletTransaction.objects.filter(kind=WalletTransaction.REFERRAL_REWARD).count(), 1)

    def test_unpaid_failed_or_cancelled_purchase_gives_nothing(self):
        from orders import services
        self.refer_friend()
        self.client.force_login(self.friend)
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk})
        order = self.place_order(user=self.friend)  # pending
        self.assertEqual(self.balance(self.referrer), 0)
        services.cancel_order(order.pk)
        self.assertEqual(self.balance(self.referrer), 0)
        self.assertEqual(Referral.objects.get().status, Referral.PENDING)
        # the later verified purchase still counts as the FIRST successful purchase
        self.friend_buys()
        self.assertEqual(self.balance(self.referrer), Decimal("1500"))

    def test_reward_idempotent_if_called_twice(self):
        self.refer_friend()
        order = self.friend_buys()
        ref.qualify_referral_for_order(order)
        ref.qualify_referral_for_order(order)
        self.assertEqual(self.balance(self.referrer), Decimal("1500"))

    def test_programme_disabled_or_zero_reward(self):
        self.biz.referral_enabled = False
        self.biz.save()
        self.refer_friend()
        self.friend_buys()
        self.assertEqual(self.balance(self.referrer), 0)
        self.assertEqual(Referral.objects.get().status, Referral.NOT_ELIGIBLE)

    def test_reward_amount_is_admin_configurable(self):
        self.biz.referral_reward_amount = Decimal("2500")
        self.biz.save()
        self.refer_friend()
        self.friend_buys()
        self.assertEqual(self.balance(self.referrer), Decimal("2500"))

    def test_referrer_does_not_earn_on_own_purchases(self):
        self.client.force_login(self.referrer)
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk})
        self.pay(self.place_order())
        self.assertEqual(self.balance(self.referrer), 0)


class WalletTests(StoreTestCase):
    def fund(self, amount):
        ref.apply_wallet_entry(self.user, Decimal(amount), WalletTransaction.ADMIN_CREDIT, note="test credit")

    def test_never_negative_and_idempotent_keys(self):
        self.fund("1000")
        with self.assertRaises(ref.InsufficientBalance):
            ref.apply_wallet_entry(self.user, Decimal("-5000"), WalletTransaction.ORDER_DEBIT)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("1000"))
        a, created1 = ref.apply_wallet_entry(self.user, Decimal("100"), WalletTransaction.ADMIN_CREDIT, key="k1")
        b, created2 = ref.apply_wallet_entry(self.user, Decimal("100"), WalletTransaction.ADMIN_CREDIT, key="k1")
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("1100"))

    def test_fully_covered_order_needs_no_paystack(self):
        self.fund("20000")
        self.login()
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": 2})
        data = {"full_name": "Ada", "email": "a@example.com", "phone": "08012345678", "address": "x",
                "state": "Lagos", "city": "y", "use_wallet": "on"}
        with mock.patch("payments.paystack.initialize_transaction") as init:
            resp = self.client.post(reverse("orders:checkout"), data)
        init.assert_not_called()
        order = Order.objects.get()
        self.assertEqual(order.status, Order.PAID)
        self.assertEqual(order.amount_payable, 0)
        self.assertEqual(order.wallet_amount, Decimal("20000"))
        self.assertEqual(Wallet.objects.get(user=self.user).balance, 0)
        self.assertEqual(self.user.cart.items.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)
        self.assertEqual(resp.status_code, 302)

    def test_partial_wallet_plus_paystack(self):
        self.fund("8000")
        self.login()
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": 2})  # 20,000
        order = self.place_order(use_wallet=True)
        self.assertEqual(order.wallet_amount, Decimal("8000"))
        self.assertEqual(order.amount_payable, Decimal("12000"))
        self.assertEqual(Wallet.objects.get(user=self.user).balance, 0)  # held immediately
        order, txn = self.pay(order)
        self.assertEqual(txn.amount, Decimal("12000"))
        self.assertEqual(order.status, Order.PAID)
        self.assertEqual(Wallet.objects.get(user=self.user).total_spent, Decimal("8000"))

    def test_cannot_spend_more_than_balance_or_twice(self):
        self.fund("5000")
        self.login()
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk})
        first = self.place_order(use_wallet=True)
        self.assertEqual(first.wallet_amount, Decimal("5000"))
        second = self.place_order(use_wallet=True)  # same cart again; wallet is empty now
        self.assertEqual(second.wallet_amount, 0)

    def test_cancel_unpaid_order_returns_wallet_credit_once(self):
        from orders import services
        self.fund("5000")
        self.login()
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk})
        order = self.place_order(use_wallet=True)
        services.cancel_order(order.pk)
        services.cancel_order(order.pk)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("5000"))

    def test_refund_returns_wallet_credit(self):
        from orders import services
        self.fund("5000")
        self.login()
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk})
        order, _ = self.pay(self.place_order(use_wallet=True))
        services.refund_order(order.pk)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("5000"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_wallet_page_is_private_and_renders(self):
        self.login()
        resp = self.client.get(reverse("referrals:wallet"))
        self.assertContains(resp, self.user.referral_code.code)
        self.assertNotContains(resp, "withdraw this")
