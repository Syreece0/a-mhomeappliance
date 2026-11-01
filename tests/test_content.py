from decimal import Decimal

from django.urls import reverse

from core.content import POLICY_SLUGS, ensure_pages
from core.models import BusinessSettings, PageRevision, PageSection, SitePage
from core.richtext import sanitize_html

from .helpers import StoreTestCase, make_product, make_user


class SanitizerTests(StoreTestCase):
    def test_scripts_handlers_and_bad_links_removed(self):
        dirty = '<p onclick="x()">Hi</p><script>alert(1)</script><a href="javascript:alert(1)">bad</a><img src=x onerror=y>'
        clean = sanitize_html(dirty)
        for bad in ("script", "onclick", "javascript:", "<img", "onerror"):
            self.assertNotIn(bad, clean)
        self.assertIn("Hi", clean)

    def test_formatting_survives(self):
        clean = sanitize_html('<h2>T</h2><ul><li>a</li></ul><a href="https://x.com">l</a>')
        self.assertIn("<h2>T</h2>", clean)
        self.assertIn("<li>a</li>", clean)
        self.assertIn('href="https://x.com"', clean)


class PublicContentTests(StoreTestCase):
    def test_all_content_pages_render(self):
        self.assertEqual(self.client.get(reverse("core:about")).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:contact")).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:policies")).status_code, 200)
        for slug in POLICY_SLUGS:
            resp = self.client.get(reverse("core:policy", args=[slug]))
            self.assertEqual(resp.status_code, 200, slug)

    def test_unknown_policy_is_404(self):
        self.assertEqual(self.client.get(reverse("core:policy", args=["nope"])).status_code, 404)

    def test_defaults_are_seeded_published_and_not_duplicated(self):
        ensure_pages()
        self.assertEqual(SitePage.objects.count(), 7)
        self.assertFalse(SitePage.objects.filter(published_at__isnull=True).exists())
        self.assertEqual(ensure_pages(), [])
        self.assertEqual(SitePage.objects.count(), 7)

    def test_footer_links_to_every_page(self):
        html = self.client.get(reverse("core:home")).content.decode()
        for url in [reverse("core:about"), reverse("core:contact")] + [reverse("core:policy", args=[s]) for s in POLICY_SLUGS]:
            self.assertIn(f'href="{url}"', html)

    def test_live_business_details_fill_the_policies(self):
        self.biz.phone, self.biz.email = "08011112222", "help@am.test"
        self.biz.payment_hold_hours = 36
        self.biz.save()
        html = self.client.get(reverse("core:policy", args=["payment-policy"])).content.decode()
        self.assertIn("08011112222", html)
        self.assertIn("36 hours", html)
        self.assertNotIn("{{", html)

    def test_no_invented_delivery_or_return_numbers(self):
        html = self.client.get(reverse("core:policy", args=["delivery-policy"])).content.decode()
        self.assertIn("confirmed by our team", html)  # fallback wording while the admin has not set an estimate
        self.biz.delivery_estimate = "2-5 working days within Lagos"
        self.biz.save()
        html = self.client.get(reverse("core:policy", args=["delivery-policy"])).content.decode()
        self.assertIn("2-5 working days within Lagos", html)

    def test_referral_policy_matches_the_real_rules(self):
        html = self.client.get(reverse("core:policy", args=["referral-policy"])).content.decode()
        self.assertIn("1,500", html)  # reward amount comes from settings
        self.assertIn("first successful, verified purchase", html)
        self.assertIn("cannot be withdrawn as cash", html)
        self.biz.referral_enabled = False
        self.biz.save()
        html = self.client.get(reverse("core:policy", args=["referral-policy"])).content.decode()
        self.assertIn("currently paused", html)

    def test_contact_page_and_footer_use_admin_details(self):
        self.biz.phone, self.biz.opening_hours, self.biz.contact_instructions = "09099998888", "Mon-Sat 9-6", "Quote your order number."
        self.biz.save()
        contact = self.client.get(reverse("core:contact")).content.decode()
        home = self.client.get(reverse("core:home")).content.decode()
        for needle in ("09099998888", "Mon-Sat 9-6"):
            self.assertIn(needle, contact)
            self.assertIn(needle, home)
        self.assertIn("Quote your order number.", contact)


class ContentManagementTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        ensure_pages()
        self.admin = make_user("boss@example.com", is_staff=True, is_superuser=True)
        self.slug = "privacy-policy"

    def _section_payload(self, **kw):
        data = {"title": "Cookies", "body": "<p>We use cookies.</p>", "is_active": "on"}
        data.update(kw)
        return data

    def test_only_authorised_admins_can_manage_content(self):
        url = reverse("dashboard:content_home")
        self.assertEqual(self.client.get(url).status_code, 302)  # anonymous -> login
        self.login()  # ordinary customer
        self.assertEqual(self.client.get(url).status_code, 403)
        staff = make_user("staff@example.com", is_staff=True)  # staff without the content permission
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(reverse("dashboard:content_page", args=[self.slug]), {"action": "publish"}).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_editor_pages_render(self):
        self.client.force_login(self.admin)
        for name, args in [("dashboard:content_home", []), ("dashboard:content_contact", []),
                           ("dashboard:content_page", [self.slug]), ("dashboard:content_page", ["about-us"]),
                           ("dashboard:content_preview", [self.slug]), ("dashboard:content_section_new", [self.slug])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)

    def test_draft_is_invisible_until_published(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:content_section_new", args=[self.slug]), self._section_payload(title="Brand New Clause"))
        page = SitePage.objects.get(slug=self.slug)
        self.assertTrue(page.has_unpublished_changes)
        public = reverse("core:policy", args=[self.slug])
        self.assertNotContains(self.client.get(public), "Brand New Clause")
        self.assertContains(self.client.get(reverse("dashboard:content_preview", args=[self.slug])), "Brand New Clause")
        self.client.post(reverse("dashboard:content_page", args=[self.slug]), {"title": page.title, "summary": page.summary, "action": "publish"})
        self.assertContains(self.client.get(public), "Brand New Clause")
        page.refresh_from_db()
        self.assertFalse(page.has_unpublished_changes)
        self.assertTrue(PageRevision.objects.filter(page=page, action=PageRevision.PUBLISHED).count() >= 2)

    def test_published_version_is_preserved_while_editing(self):
        self.client.force_login(self.admin)
        page = SitePage.objects.get(slug=self.slug)
        old_title = page.published_snapshot["sections"][0]["title"]
        sec = page.sections.first()
        self.client.post(reverse("dashboard:content_section_edit", args=[self.slug, sec.pk]), self._section_payload(title="Rewritten"))
        self.assertContains(self.client.get(reverse("core:policy", args=[self.slug])), old_title)
        self.assertNotContains(self.client.get(reverse("core:policy", args=[self.slug])), "Rewritten")

    def test_discard_returns_to_published_version(self):
        self.client.force_login(self.admin)
        page = SitePage.objects.get(slug=self.slug)
        n = page.sections.count()
        self.client.post(reverse("dashboard:content_section_new", args=[self.slug]), self._section_payload())
        self.assertEqual(page.sections.count(), n + 1)
        self.client.post(reverse("dashboard:content_page", args=[self.slug]), {"action": "discard"})
        page.refresh_from_db()
        self.assertEqual(page.sections.count(), n)
        self.assertFalse(page.has_unpublished_changes)

    def test_dangerous_markup_is_stripped_on_save(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:content_section_new", args=[self.slug]),
                         self._section_payload(body='<p>ok</p><script>alert(1)</script><a href="javascript:x()">z</a>'))
        body = PageSection.objects.get(title="Cookies").body
        self.assertNotIn("script", body)
        self.assertNotIn("javascript", body)
        self.assertIn("ok", body)

    def test_overlong_or_empty_section_rejected(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("dashboard:content_section_new", args=[self.slug]),
                                self._section_payload(body="<p>" + "x" * 50000 + "</p>"))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PageSection.objects.filter(title="Cookies").exists())
        resp = self.client.post(reverse("dashboard:content_section_new", args=[self.slug]), self._section_payload(body="<p> </p>"))
        self.assertEqual(resp.status_code, 200)

    def test_hidden_removed_and_reordered_sections(self):
        self.client.force_login(self.admin)
        page = SitePage.objects.get(slug=self.slug)
        first, second = list(page.sections.order_by("position", "id")[:2])
        self.client.post(reverse("dashboard:content_section_move", args=[self.slug, second.pk]), {"direction": "up"})
        self.assertEqual(page.sections.order_by("position", "id").first().pk, second.pk)
        self.client.post(reverse("dashboard:content_section_delete", args=[self.slug, first.pk]))
        self.assertFalse(PageSection.objects.filter(pk=first.pk).exists())
        # the live page still shows the removed section until publish
        self.assertContains(self.client.get(reverse("core:policy", args=[self.slug])), first.title)

    def test_contact_form_updates_business_settings(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("dashboard:content_contact"), {
            "phone": "08000000001", "whatsapp_number": "2348000000002", "email": "new@am.test", "address": "5 Test Road",
            "opening_hours": "Daily 8-8", "contact_instructions": "Hello", "facebook_url": "", "instagram_url": "",
            "twitter_url": "", "tiktok_url": "", "youtube_url": "",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(BusinessSettings.load().phone, "08000000001")
        self.assertContains(self.client.get(reverse("core:contact")), "Daily 8-8")

    def test_changes_are_logged(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:content_section_new", args=[self.slug]), self._section_payload())
        self.assertTrue(PageRevision.objects.filter(page__slug=self.slug, action=PageRevision.DRAFT, user=self.admin).exists())


class ShopLayoutAndFilterTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.lg = make_product("LG Washer", "150000", brand="LG", stock=0)
        self.sam = make_product("Samsung Fridge", "200000", brand="Samsung", previous_price="250000")

    def test_filters_are_horizontal_beside_the_title_and_no_sidebar_or_category_box(self):
        html = self.client.get(reverse("catalog:list")).content.decode()
        self.assertIn('class="filter-bar"', html)
        self.assertIn("shop-title", html)
        self.assertLess(html.index("shop-title"), html.index('class="filter-bar"'))
        self.assertNotIn('class="filters"', html)
        self.assertNotIn('aria-label="Categories"><h4>', html)

    def test_availability_filter_both_ways(self):
        url = reverse("catalog:list")
        self.assertNotContains(self.client.get(url, {"availability": "in_stock"}), "LG Washer")
        out = self.client.get(url, {"availability": "out_of_stock"})
        self.assertContains(out, "LG Washer")
        self.assertNotContains(out, "Samsung Fridge")

    def test_sort_oldest_and_newest(self):
        url = reverse("catalog:list")
        newest = [p.name for p in self.client.get(url, {"sort": "newest"}).context["products"]]
        oldest = [p.name for p in self.client.get(url, {"sort": "oldest"}).context["products"]]
        self.assertEqual(newest, list(reversed(oldest)))

    def test_filters_combine_and_clear_link_appears(self):
        resp = self.client.get(reverse("catalog:list"), {"brand": "Samsung", "discounted": "1", "min_price": "100000"})
        self.assertContains(resp, "Samsung Fridge")
        self.assertNotContains(resp, "LG Washer")
        self.assertTrue(resp.context["filters_active"])
        self.assertContains(resp, "Clear Filters")
        self.assertNotContains(self.client.get(reverse("catalog:list")), "Clear Filters")

    def test_brand_list_is_limited_to_the_category(self):
        from catalog.models import Category

        laundry = Category.objects.create(name="Laundry")
        make_product("Washer X", "90000", brand="Hisense", category=laundry)
        resp = self.client.get(reverse("catalog:list"), {"category": laundry.slug})
        self.assertEqual(list(resp.context["brands"]), ["Hisense"])


class ThemeDefaultTests(StoreTestCase):
    def test_light_is_the_default_and_os_dark_preference_is_ignored(self):
        html = self.client.get(reverse("core:home")).content.decode()
        self.assertIn('data-theme="light"', html)
        self.assertNotIn("prefers-color-scheme", html)
        self.assertIn('id="theme-toggle"', html)
