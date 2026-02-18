from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.views.generic import RedirectView

from schedule import crm_views

admin.site.site_header = "WOOM FIT — Админка"
admin.site.site_title = "WOOM FIT"
admin.site.index_title = "Управление"

urlpatterns = [
    # ✅ ВАЖНО: planning ДО admin.site.urls
    path("admin/planning/", crm_views.planning, name="crm_planning"),
    path("admin/planning/move/", crm_views.move_session, name="crm_planning_move"),
    path("admin/planning/repeat-week/", crm_views.repeat_week, name="crm_planning_repeat_week"),


    path("admin/", admin.site.urls),

    # Совместимость со стандартным Django redirect после логина.
    path("accounts/profile/", RedirectView.as_view(url="/profile/", permanent=False)),

    path("", include("core.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("profile/", include("accounts.urls")),
    path("schedule/", include("schedule.urls")),
    path("shop/", include("shop.urls")),
    path("orders/", include("orders.urls")),
    path("payments/", include("payments.urls")),
    path("news/", include(("news.urls", "news"), namespace="news")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
