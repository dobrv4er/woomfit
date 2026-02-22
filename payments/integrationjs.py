import json
from typing import Any

from django.http import HttpRequest


def is_widget_request(request: HttpRequest) -> bool:
    return request.method == "POST" and request.POST.get("integration_widget") == "1"


def parse_widget_method_data(request: HttpRequest) -> dict[str, Any]:
    raw = (request.POST.get("widget_method_data") or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def build_widget_init_data(request: HttpRequest) -> dict[str, str] | None:
    if not is_widget_request(request):
        return None

    data = {"connection_type": "Widget"}

    method_data = parse_widget_method_data(request)
    payment_type = method_data.get("paymentType")
    if payment_type is not None:
        data["widget_payment_type"] = str(payment_type)[:64]

    widget_name = method_data.get("widgetName")
    if widget_name is not None:
        data["widget_name"] = str(widget_name)[:64]

    return data
