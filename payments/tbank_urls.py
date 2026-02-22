from django.conf import settings
from django.http import HttpRequest
from django.urls import reverse


def _configured_url(name: str) -> str:
    return str(getattr(settings, name, "") or "").strip()


def notification_url(request: HttpRequest) -> str:
    configured = _configured_url("TBANK_NOTIFICATION_URL")
    if configured:
        return configured
    return request.build_absolute_uri(reverse("payments:tbank_webhook"))


def success_url(request: HttpRequest, *, setting_name: str, view_name: str, args: list | None = None) -> str:
    configured = _configured_url(setting_name)
    if configured:
        return configured
    return request.build_absolute_uri(reverse(view_name, args=args or []))


def fail_url(request: HttpRequest, *, setting_name: str, view_name: str, args: list | None = None) -> str:
    configured = _configured_url(setting_name)
    if configured:
        return configured
    return request.build_absolute_uri(reverse(view_name, args=args or []))
