from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.overview, name="overview"),
    # products & inventory
    path("products/", views.product_list, name="product_list"),
    path("products/new/", views.product_edit, name="product_new"),
    path("products/<int:pk>/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),
    path("products/<int:pk>/stock/", views.product_stock, name="product_stock"),
    path("products/<int:pk>/images/<int:image_id>/", views.product_image_action, name="product_image"),
    path("inventory/", views.inventory_log, name="inventory_log"),
    # categories
    path("categories/", views.category_list, name="category_list"),
    path("categories/new/", views.category_edit, name="category_new"),
    path("categories/<int:pk>/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("categories/<int:pk>/move/", views.category_move, name="category_move"),
    # orders & payments
    path("orders/", views.order_list, name="order_list"),
    path("orders/<str:number>/", views.order_detail, name="order_detail"),
    path("orders/<str:number>/status/", views.order_status, name="order_status"),
    path("orders/<str:number>/clear-flag/", views.order_clear_flag, name="order_clear_flag"),
    path("transactions/", views.transactions, name="transactions"),
    # customers & referrals
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/toggle-active/", views.customer_toggle_active, name="customer_toggle"),
    path("customers/<int:pk>/wallet/", views.wallet_adjust, name="wallet_adjust"),
    path("referrals/", views.referral_admin, name="referrals"),
    # promotions, banners, reviews
    path("promotions/", views.promotion_list, name="promotion_list"),
    path("promotions/new/", views.promotion_edit, name="promotion_new"),
    path("promotions/<int:pk>/", views.promotion_edit, name="promotion_edit"),
    path("promotions/<int:pk>/delete/", views.promotion_delete, name="promotion_delete"),
    path("banners/", views.banner_list, name="banner_list"),
    path("banners/new/", views.banner_edit, name="banner_new"),
    path("banners/<int:pk>/", views.banner_edit, name="banner_edit"),
    path("banners/<int:pk>/delete/", views.banner_delete, name="banner_delete"),
    path("reviews/", views.review_list, name="review_list"),
    path("reviews/<int:pk>/", views.review_action, name="review_action"),
    # email
    path("campaigns/", views.campaign_list, name="campaign_list"),
    path("campaigns/new/", views.campaign_edit, name="campaign_new"),
    path("campaigns/<int:pk>/", views.campaign_edit, name="campaign_edit"),
    path("campaigns/<int:pk>/preview/", views.campaign_preview, name="campaign_preview"),
    path("campaigns/<int:pk>/action/", views.campaign_action, name="campaign_action"),
    path("emails/", views.email_history, name="email_history"),
    path("emails/<int:pk>/retry/", views.email_retry, name="email_retry"),
    path("automation/", views.abandoned_cart_settings, name="abandoned_cart"),
    # website content (About, policies, contact)
    path("content/", views.content_home, name="content_home"),
    path("content/contact/", views.content_contact, name="content_contact"),
    path("content/pages/<slug:slug>/", views.content_page, name="content_page"),
    path("content/pages/<slug:slug>/preview/", views.content_preview, name="content_preview"),
    path("content/pages/<slug:slug>/sections/new/", views.content_section_edit, name="content_section_new"),
    path("content/pages/<slug:slug>/sections/<int:pk>/", views.content_section_edit, name="content_section_edit"),
    path("content/pages/<slug:slug>/sections/<int:pk>/delete/", views.content_section_delete, name="content_section_delete"),
    path("content/pages/<slug:slug>/sections/<int:pk>/move/", views.content_section_move, name="content_section_move"),
    # settings
    path("settings/", views.business_settings, name="settings"),
]
