# A&M Home Appliances - Django e-commerce platform

Django 5.1+, PostgreSQL, Cloudinary, Paystack, Celery + Redis. Navy / white / gold, light and dark mode.

> **STATUS: WRITTEN, NOT YET RUN.** This code was produced in an environment with no access to PyPI, so
> Django could not be installed and nothing has been executed - not the server, not migrations, not the tests.
> Only Python syntax, URL-name and template-reference consistency were checked statically. Expect a few
> small errors on first run. Follow "First run" below and send any traceback back for fixing.

## First run

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                      # then edit (SECRET_KEY, Paystack test keys, ...)

# 1. Generate the database migrations (they are not pre-generated; this must come before tests/migrate)
python manage.py makemigrations accounts core catalog inventory cart wishlist orders payments referrals notifications marketing

# 2. Run the test suite - it exercises payments, referrals, wallet, cart clearance, permissions
python manage.py test --settings=config.test_settings

# 3. Create the database schema
python manage.py migrate

# 4. Load data and run
python manage.py seed_categories                          # the 8 A&M categories + subcategories
python manage.py createsuperuser                          # email login; make this user staff
python manage.py runserver
```

* With no `DATABASE_URL` pointing to Postgres the project falls back to SQLite so you can try it quickly.
  Use PostgreSQL in production: `DATABASE_URL=postgres://user:pass@host:5432/dbname`.
* Admin dashboard: `/manage/` (staff only). Raw Django admin: `/django-admin/`.
* Put the Paystack **webhook URL** `https://YOUR-DOMAIN/payments/webhook/` in your Paystack dashboard
  (test and live are configured separately). The `PAYSTACK_MODE` variable selects which key pair is used.
* Emails print to the console in development (`EMAIL_BACKEND=...console...`). `CELERY_EAGER=True` runs
  background jobs inline so no worker is needed. In production set `CELERY_EAGER=False` and run:
  `celery -A config worker -l info` and `celery -A config beat -l info` (Redis required).
* Cloudinary: set `CLOUDINARY_URL`; leave it empty to store uploads on local disk.
* Production: `DJANGO_DEBUG=False`, a real `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`,
  `gunicorn config.wsgi`, `python manage.py collectstatic`.

## Upgrading an existing install (website-content update)

The About / policy / contact update adds database tables and four settings fields, so after copying the new
files over your project run:

```bash
python manage.py makemigrations core          # creates the new migration for SitePage / PageSection / PageRevision
python manage.py migrate
python manage.py test --settings=config.test_settings
python manage.py runserver
```

* The About Us page and the six policies are created automatically (and published) the first time anyone opens
  them; `python manage.py seed_content` does the same on demand. Existing pages are never overwritten.
* **Dashboard > Website content** (`/manage/content/`) is where the admin edits About Us, every policy and the
  contact details. Edits are saved as a *draft*; visitors only see them after **Publish**. Preview, discard-draft and a
  change history are on each page. Only superusers, or staff who were given the *"Can change site page"*
  permission in `/django-admin/`, can use it.
* Policy text can contain live details such as `{{phone}}`, `{{email}}`, `{{referral_reward}}` or
  `{{payment_hold_hours}}` (use **Insert detail** in the editor). They come from Settings / Contact information,
  so numbers are never hard-coded. Delivery period and return period are set in *Website content > Policy details*;
  if left empty, the policy says the period is confirmed by the team.
* **Logo:** upload it in `/manage/settings/` (Business settings > logo). It is shown on a white chip in the navy header,
  footer and emails so it stays visible in light and dark mode. No logo file ships with the project.
* The default policy wording is a sensible starting point written to match how the store works. It is **not legal
  advice** - read it, edit it, and have it reviewed before you rely on it.

## Where things live

| App | Responsibility |
|---|---|
| `core` | Business settings (singleton), banners, About / policy / contact pages (`SitePage`, draft + publish), referral-link capture |
| `accounts` | Email-login user (also the customer profile), registration, password reset |
| `catalog` | Categories, products, images, reviews, scheduled promotions |
| `inventory` | Stock ledger; all stock changes go through `inventory.services` |
| `cart`, `wishlist` | Cart (+ clear-purchased logic, abandoned-cart task), wishlist |
| `orders` | Checkout, order lifecycle, cancel / refund / status rules (`orders.services`) |
| `payments` | Paystack client, verification, webhook, idempotency (`payments.services`) |
| `referrals` | Referral codes, attribution, wallet + ledger, first-purchase reward rules |
| `notifications` | In-site notification centre, email queue/delivery records/retry, event triggers |
| `marketing` | Newsletter, campaigns, scheduling, unsubscribe |
| `dashboard` | Staff-only management UI, including Website content (About, policies, contact) |

## Key rules and where they are enforced

* **Payment is never trusted from the browser.** The callback and webhook both call Paystack's verify API;
  the amount and currency must match the stored transaction (`payments/services.py::apply_verification`).
  Webhooks are HMAC-SHA512 signature checked and de-duplicated.
* **Cart clearance / stock deduction / referral reward** happen once, in `orders/services.py::finalize_paid_order`,
  after verified payment (or for an order fully covered by wallet credit). Only purchased quantities leave the cart.
* **Referral reward**: only for the referred customer's *first verified purchase*, once per referred customer
  (`Referral.referred` is unique, attribution is immutable, reward uses an idempotency key and a row lock).
  Registration and link visits pay nothing. Reward amount / on-off / minimum order are admin settings.
* **Wallet**: credit is debited when the order is placed (a hold), returned on cancel / expiry / refund, never
  negative (DB check constraint + row lock), every movement recorded in `WalletTransaction`.
* **Marketing email is opt-in** and separate from transactional email; unsubscribe is global and re-checked at send time.

## Feature status

Everything in the spec sections provided (7-27) has code. **None of it has been run.** Items the spec's missing
sections 1-6 may have defined differently (stack versions, exact branding, any page I assumed) were assumed - see below.

Known limitations / decisions to review:

1. No migrations are committed (could not run `makemigrations`); generate them as shown above.
2. No product photography is bundled - upload product, banner and category images in the dashboard
   (a neutral placeholder shows until you do).
3. Card refunds must still be issued in the Paystack dashboard; the platform flags the order and restores
   stock / wallet credit when you mark it Refunded.
4. "Buy now" adds the item to the cart then checks out only that line (its full cart quantity).
5. Promotional "customer groups" are the audience choices on a campaign (all opted-in, subscribers, customers, past buyers).
6. Mobile layout, dark mode and animations were written to the spec but have not been viewed in a browser.
7. Sections 1-6 of the spec were not in the file I received.
