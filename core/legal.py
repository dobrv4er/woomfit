from django.http import HttpRequest


TRUTHY_VALUES = {"1", "true", "yes", "on", "y"}


def is_checked(request: HttpRequest, field_name: str) -> bool:
    raw = str(request.POST.get(field_name, "")).strip().lower()
    return raw in TRUTHY_VALUES


def client_ip(request: HttpRequest) -> str | None:
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    real_ip = (request.META.get("HTTP_X_REAL_IP") or "").strip()
    if real_ip:
        return real_ip
    remote_addr = (request.META.get("REMOTE_ADDR") or "").strip()
    return remote_addr or None
