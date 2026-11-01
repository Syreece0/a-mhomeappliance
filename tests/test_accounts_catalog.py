from django.core import mail
from django.urls import reverse

from accounts.models import User
from catalog.models import Review
from notifications.models import EmailDelivery, Notification
from referrals.models import ReferralCode, Wallet

from .helpers import StoreTestCase, make_product, make_user


class AccountTests(StoreTestCase):
    def test_registration_creates_code_wallet_and_welcome_email(self):
        resp = self.client.post(reverse("accounts:register"), {
            "first_name": "New", "last_name": "User", "email": "New@Example.com", "phone": "08099999999",
            "password1": "Str0ng-pass!", "password2": "Str0ng-pass!",
        })
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(email="new@example.com")
        self.assertTrue(ReferralCode.objects.filter(user=user).exists())
        self.assertTrue(Wallet.objects.filter(user=user).exists())
        self.assertFalse(user.marketing_opt_in, "marketing must be opt-in")
        self.assertTrue(any("Welcome" in m.subject for m in mail.outbox))
        self.assertTrue(Notification.objects.filter(user=user, title__icontains="Welcome").exists())

    def test_duplicate_email_rejected_case_insensitive(self):
        resp = self.client.post(reverse("accounts:register"), {
            "first_name": "X", "last_name": "Y", "email": "A@EXAMPLE.COM", "phone": "08011111111",
            "password1": "Str0ng-pass!", "password2": "Str0ng-pass!",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.filter(email__iexact="a@example.com").count(), 1)

    def test_login_logout_and_protected_pages(self):
        self.assertEqual(self.client.get(reverse("orders:list")).status_code, 302)
        ok = self.client.post(reverse("accounts:login"), {"username": "a@example.com", "password": "Str0ng-pass!"})
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(self.client.get(reverse("orders:list")).status_code, 200)
        self.client.post(reverse("accounts:logout"))
        self.assertEqual(self.client.get(reverse("orders:list")).status_code, 302)

    def test_password_reset_email_sent(self):
        self.client.post(reverse("accounts:password_reset"), {"email": "a@example.com"})
        self.assertTrue(any("Reset your" in m.subject for m in mail.outbox))
        body = [m for m in mail.outbox if "Reset your" in m.subject][0].body
        self.assertIn("/accounts/password/reset/", body)

    def test_pages_render(self):
        for name in ["core:home", "catalog:list", "accounts:login", "accounts:register"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        # account pages require login
        self.assertEqual(self.client.get(reverse("wishlist:list")).status_code, 302)
        self.login()
        for name in ["wishlist:list", "accounts:dashboard", "accounts:profile", "cart:detail", "orders:list",
                     "referrals:wallet", "notifications:list"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("orders:checkout")).status_code, 302)  # empty cart -> back to cart


class CatalogTests(StoreTestCase):
    def test_search_filter_sort(self):
        make_product("Samsung Fridge", "200000", brand="Samsung", previous_price="250000")
        make_product("LG Washer", "150000", brand="LG", stock=0)
        url = reverse("catalog:list")
        self.assertContains(self.client.get(url, {"q": "samsung"}), "Samsung Fridge")
        self.assertNotContains(self.client.get(url, {"q": "samsung"}), "LG Washer")
        self.assertNotContains(self.client.get(url, {"availability": "in_stock"}), "LG Washer")
        self.assertContains(self.client.get(url, {"discounted": "1"}), "Samsung Fridge")
        self.assertNotContains(self.client.get(url, {"discounted": "1"}), "Blender")
        self.assertNotContains(self.client.get(url, {"min_price": "100000"}), "Blender")
        resp = self.client.get(url, {"sort": "price_asc"})
        names = [p.name for p in resp.context["products"]]
        self.assertEqual(names[0], "Blender")

    def test_hidden_products_not_listed(self):
        make_product("Secret", is_available=False)
        self.assertNotContains(self.client.get(reverse("catalog:list")), "Secret")

    def test_product_detail_and_discount(self):
        p = make_product("Kettle", "8000", previous_price="10000")
        self.assertEqual(p.discount_percent, 20)
        self.assertContains(self.client.get(p.get_absolute_url()), "Kettle")

    def test_review_requires_verified_purchase(self):
        self.login()
        url = reverse("catalog:review", args=[self.product.slug])
        self.client.post(url, {"rating": 5, "title": "Great", "body": "Nice"})
        self.assertEqual(Review.objects.count(), 0)
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk})
        order = self.place_order()
        self.pay(order)
        self.client.post(url, {"rating": 5, "title": "Great", "body": "Nice"})
        review = Review.objects.get()
        self.assertTrue(review.is_verified_purchase)
        self.assertFalse(review.is_approved, "reviews wait for moderation")


class CartWishlistTests(StoreTestCase):
    def test_add_update_remove(self):
        self.login()
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": 2})
        self.assertEqual(self.user.cart.items.get().quantity, 2)
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk})  # no duplicate line
        self.assertEqual(self.user.cart.items.count(), 1)
        self.assertEqual(self.user.cart.items.get().quantity, 3)
        self.client.post(reverse("cart:update"), {"product_id": self.product.pk, "quantity": 5})
        self.assertEqual(self.user.cart.items.get().quantity, 5)
        self.client.post(reverse("cart:remove"), {"product_id": self.product.pk})
        self.assertEqual(self.user.cart.items.count(), 0)

    def test_cannot_exceed_stock(self):
        self.login()
        resp = self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": 99},
                                HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 400)
        from cart.models import CartItem
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 0)

    def test_anonymous_add_goes_to_login(self):
        resp = self.client.post(reverse("cart:add"), {"product_id": self.product.pk})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp["Location"])

    def test_wishlist_toggle_and_move_to_cart(self):
        self.login()
        self.client.post(reverse("wishlist:toggle"), {"product_id": self.product.pk})
        self.assertEqual(self.user.wishlist_items.count(), 1)
        self.client.post(reverse("wishlist:move_to_cart"), {"product_id": self.product.pk})
        self.assertEqual(self.user.wishlist_items.count(), 0)
        self.assertEqual(self.user.cart.items.count(), 1)
        self.client.post(reverse("wishlist:toggle"), {"product_id": self.product.pk})
        self.client.post(reverse("wishlist:toggle"), {"product_id": self.product.pk})
        self.assertEqual(self.user.wishlist_items.count(), 0)


class NotificationTests(StoreTestCase):
    def test_bell_feed_and_mark_read_are_private(self):
        other = make_user("other@example.com")
        n = Notification.objects.create(user=other, title="Secret")
        self.login()
        self.assertEqual(self.client.get(reverse("notifications:open", args=[n.pk])).status_code, 404)
        self.client.post(reverse("notifications:mark_read", args=[n.pk]))
        n.refresh_from_db()
        self.assertFalse(n.is_read)
        mine = Notification.objects.create(user=self.user, title="Mine")
        data = self.client.get(reverse("notifications:latest")).json()
        self.assertGreaterEqual(data["unread"], 1)
        self.client.post(reverse("notifications:mark_all"))
        mine.refresh_from_db()
        self.assertTrue(mine.is_read)
