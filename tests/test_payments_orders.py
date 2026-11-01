import hashlib
import hmac
import json
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.urls import reverse

from cart.models import CartItem
from catalog.models import Product
from inventory.models import InventoryMovement
from notifications.models import EmailDelivery
from orders.models import Order
from payments.models import PaymentTransaction, WebhookEvent
from payments import services as pay_services

from .helpers import StoreTestCase, make_product, make_user, paystack_ok


class CheckoutAndPaymentTests(StoreTestCase):
    def fill_cart(self, qty=2):
        self.login()
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": qty})

    def test_checkout_creates_pending_order_and_redirects_to_paystack(self):
        self.fill_cart()
        data = {"full_name": "Ada Obi", "email": "a@example.com", "phone": "08012345678", "address": "1 Road",
                "state": "Lagos", "city": "Ikeja"}
        with mock.patch("payments.paystack.initialize_transaction",
                        return_value={"authorization_url": "https://paystack.test/pay", "access_code": "x"}) as init:
            resp = self.client.post(reverse("orders:checkout"), data)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "https://paystack.test/pay")
        order = Order.objects.get()
        self.assertEqual(order.status, Order.PAYMENT_PENDING)
        self.assertEqual(order.amount_payable, Decimal("20000"))
        self.assertEqual(init.call_args.kwargs["amount"], Decimal("20000"))
        # nothing is cleared or deducted before payment is verified
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_successful_payment_clears_only_purchased_items_and_reduces_stock(self):
        other = make_product("Toaster", "5000", stock=4)
        self.fill_cart(2)
        self.client.post(reverse("cart:add"), {"product_id": other.pk, "quantity": 1})
        order = self.place_order(only=self.product.pk)  # buy only the blender
        self.assertEqual(order.items.count(), 1)
        order, txn = self.pay(order)
        self.assertEqual(order.status, Order.PAID)
        self.assertEqual(txn.status, PaymentTransaction.SUCCESS)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)
        self.assertEqual(self.product.sold_count, 2)
        remaining = CartItem.objects.filter(cart__user=self.user)
        self.assertEqual([c.product_id for c in remaining], [other.pk], "unpurchased item must stay")
        self.assertTrue(InventoryMovement.objects.filter(product=self.product, change=-2, order=order).exists())
        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(any("Payment confirmed" in s for s in subjects))

    def test_partial_quantity_stays_in_cart(self):
        self.fill_cart(5)
        order = self.place_order()
        # customer changes mind: cart edited after order placed - purchased qty 5, cart now has 7
        self.client.post(reverse("cart:update"), {"product_id": self.product.pk, "quantity": 7})
        self.pay(order)
        self.assertEqual(CartItem.objects.get(cart__user=self.user).quantity, 2)

    def test_double_verification_is_idempotent(self):
        self.fill_cart(1)
        order, txn = self.pay(self.place_order())
        with mock.patch("payments.paystack.verify_transaction", return_value=paystack_ok(txn.reference, txn.amount)):
            pay_services.verify_and_process(txn.reference)
            pay_services.verify_and_process(txn.reference)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)
        self.assertEqual(len([m for m in mail.outbox if "Payment confirmed" in m.subject]), 1)

    def test_failed_payment_keeps_cart_and_sends_email(self):
        self.fill_cart(1)
        order = self.place_order()
        with mock.patch("payments.paystack.initialize_transaction",
                        return_value={"authorization_url": "https://p.test/x", "access_code": "a"}):
            pay_services.start_payment(order, "http://testserver/cb/")
        txn = PaymentTransaction.objects.get()
        with mock.patch("payments.paystack.verify_transaction",
                        return_value={"status": "failed", "gateway_response": "Insufficient funds", "id": 5}):
            pay_services.verify_and_process(txn.reference)
        order.refresh_from_db()
        txn.refresh_from_db()
        self.assertEqual(txn.status, PaymentTransaction.FAILED)
        self.assertEqual(order.status, Order.PAYMENT_PENDING)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        failed = [m for m in mail.outbox if "unsuccessful" in m.subject]
        self.assertEqual(len(failed), 1)
        self.assertIn("Retry Payment", failed[0].alternatives[0][0])

    def test_pending_or_abandoned_never_clear_cart(self):
        self.fill_cart(1)
        order = self.place_order()
        with mock.patch("payments.paystack.initialize_transaction",
                        return_value={"authorization_url": "https://p.test/x", "access_code": "a"}):
            pay_services.start_payment(order, "http://testserver/cb/")
        txn = PaymentTransaction.objects.get()
        for status in ("ongoing", "abandoned"):
            with mock.patch("payments.paystack.verify_transaction", return_value={"status": status}):
                pay_services.verify_and_process(txn.reference)
            order.refresh_from_db()
            self.assertIsNone(order.paid_at)
            self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 1)

    def test_amount_mismatch_is_rejected(self):
        self.fill_cart(1)
        order = self.place_order()
        with mock.patch("payments.paystack.initialize_transaction",
                        return_value={"authorization_url": "https://p.test/x", "access_code": "a"}):
            pay_services.start_payment(order, "http://testserver/cb/")
        txn = PaymentTransaction.objects.get()
        with mock.patch("payments.paystack.verify_transaction", return_value=paystack_ok(txn.reference, "1")):
            pay_services.verify_and_process(txn.reference)
        order.refresh_from_db()
        self.assertIsNone(order.paid_at)
        self.assertTrue(order.needs_attention)

    def test_callback_ignores_browser_claims_and_verifies(self):
        self.fill_cart(1)
        order = self.place_order()
        with mock.patch("payments.paystack.initialize_transaction",
                        return_value={"authorization_url": "https://p.test/x", "access_code": "a"}):
            pay_services.start_payment(order, "http://testserver/cb/")
        txn = PaymentTransaction.objects.get()
        with mock.patch("payments.paystack.verify_transaction", return_value={"status": "abandoned"}):
            self.client.get(reverse("payments:callback"), {"reference": txn.reference, "status": "success"})
        order.refresh_from_db()
        self.assertIsNone(order.paid_at)

    def test_callback_for_another_users_reference_is_404(self):
        self.fill_cart(1)
        order = self.place_order()
        with mock.patch("payments.paystack.initialize_transaction",
                        return_value={"authorization_url": "https://p.test/x", "access_code": "a"}):
            pay_services.start_payment(order, "http://testserver/cb/")
        txn = PaymentTransaction.objects.get()
        self.client.force_login(make_user("thief@example.com"))
        self.assertEqual(self.client.get(reverse("payments:callback"), {"reference": txn.reference}).status_code, 404)

    def test_out_of_stock_blocks_checkout(self):
        self.fill_cart(2)
        Product.objects.filter(pk=self.product.pk).update(stock=1)
        resp = self.client.post(reverse("orders:checkout"), {
            "full_name": "A", "email": "a@example.com", "phone": "08012345678", "address": "x", "state": "Lagos", "city": "y"})
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(resp.status_code, 302)


class WebhookTests(StoreTestCase):
    def _signed(self, payload):
        raw = json.dumps(payload).encode()
        sig = hmac.new(b"sk_test_unit_tests", raw, hashlib.sha512).hexdigest()
        return raw, sig

    def _pending(self):
        self.login()
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk})
        order = self.place_order()
        with mock.patch("payments.paystack.initialize_transaction",
                        return_value={"authorization_url": "https://p.test/x", "access_code": "a"}):
            pay_services.start_payment(order, "http://testserver/cb/")
        return order, PaymentTransaction.objects.get()

    def test_bad_signature_rejected(self):
        raw, _ = self._signed({"event": "charge.success", "data": {"reference": "x"}})
        resp = self.client.post(reverse("payments:webhook"), raw, content_type="application/json",
                                HTTP_X_PAYSTACK_SIGNATURE="deadbeef")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(WebhookEvent.objects.count(), 0)

    def test_valid_webhook_verifies_with_paystack_then_pays(self):
        order, txn = self._pending()
        raw, sig = self._signed({"event": "charge.success", "data": {"reference": txn.reference, "id": 99}})
        with mock.patch("payments.paystack.verify_transaction", return_value=paystack_ok(txn.reference, txn.amount)):
            resp = self.client.post(reverse("payments:webhook"), raw, content_type="application/json",
                                    HTTP_X_PAYSTACK_SIGNATURE=sig)
            again = self.client.post(reverse("payments:webhook"), raw, content_type="application/json",
                                     HTTP_X_PAYSTACK_SIGNATURE=sig)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(again.content, b"already processed")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.PAID)

    def test_webhook_claiming_success_but_paystack_says_failed(self):
        order, txn = self._pending()
        raw, sig = self._signed({"event": "charge.success", "data": {"reference": txn.reference, "id": 1}})
        with mock.patch("payments.paystack.verify_transaction", return_value={"status": "failed"}):
            self.client.post(reverse("payments:webhook"), raw, content_type="application/json",
                             HTTP_X_PAYSTACK_SIGNATURE=sig)
        order.refresh_from_db()
        self.assertIsNone(order.paid_at)


class OrderLifecycleTests(StoreTestCase):
    def paid_order(self, qty=2):
        self.login()
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": qty})
        return self.pay(self.place_order())[0]

    def test_status_flow_and_emails(self):
        from orders import services
        order = self.paid_order()
        staff = make_user("staff@example.com", is_staff=True)
        for status in (Order.PROCESSING, Order.SHIPPED, Order.DELIVERED):
            services.set_status(order.pk, status, by=staff, carrier="DHL", tracking_number="T1")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.DELIVERED)
        self.assertTrue(any("shipped" in m.subject.lower() for m in mail.outbox))
        self.assertTrue(any("delivered" in m.subject.lower() for m in mail.outbox))
        with self.assertRaises(services.OrderError):
            services.set_status(order.pk, Order.PROCESSING)

    def test_cancel_paid_order_restores_stock_once(self):
        from orders import services
        order = self.paid_order(3)
        services.cancel_order(order.pk)
        services.cancel_order(order.pk)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_customer_cannot_view_or_cancel_others_orders(self):
        order = self.paid_order()
        self.client.force_login(make_user("snoop@example.com"))
        self.assertEqual(self.client.get(reverse("orders:detail", args=[order.number])).status_code, 404)
        self.assertEqual(self.client.post(reverse("orders:cancel", args=[order.number])).status_code, 404)

    def test_unpaid_order_cancel_by_customer(self):
        self.login()
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk})
        order = self.place_order()
        self.client.post(reverse("orders:cancel", args=[order.number]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.CANCELLED)

    def test_order_numbers_unique(self):
        self.login()
        numbers = set()
        for _ in range(5):
            self.client.post(reverse("cart:add"), {"product_id": self.product.pk})
            numbers.add(self.place_order().number)
        self.assertEqual(len(numbers), 5)
