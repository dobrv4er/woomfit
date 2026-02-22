import hashlib
import os
import requests


class TBankClient:
    def __init__(self, terminal_key, password, is_test=True):
        self.terminal_key = terminal_key
        self.password = password
        # According to current T-Bank eAcq API docs (2026),
        # Init/Confirm/etc are served from securepay.tinkoff.ru for both test and prod.
        # Keep env override to simplify emergency switch without code edits.
        default_base = "https://securepay.tinkoff.ru/v2"
        self.base_url = (
            os.getenv("TBANK_API_BASE_URL_TEST", default_base).strip()
            if is_test
            else os.getenv("TBANK_API_BASE_URL", default_base).strip()
        )

    @staticmethod
    def _token_value_to_string(value) -> str:
        # T-Bank notifications include JSON booleans (true/false).
        # Python str(True/False) gives "True"/"False", which breaks token check.
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _token(self, payload: dict) -> str:
        data = payload.copy()
        data["Password"] = self.password

        # Token algorithm (T‑Bank): only root-level scalar params participate.
        # Nested objects/arrays like Receipt and DATA MUST NOT be included.
        # Ref: "Токен" in T‑Bank Dev Portal.
        parts = []
        for k in sorted(data.keys()):
            v = data[k]
            if v is None:
                continue
            # Skip nested objects/arrays
            if isinstance(v, (dict, list, tuple)):
                continue
            parts.append(self._token_value_to_string(v))

        raw = "".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()

    def validate_notification(self, payload: dict) -> bool:
        """Validate incoming webhook notification from T-Bank.

        Token algorithm is the same as for Init, but the incoming payload
        already contains Token. We must:
        - remove Token
        - add Password
        - sort keys and concatenate values
        - sha256 and compare with provided Token

        Returns False if Token is missing/invalid.
        """
        if not isinstance(payload, dict):
            return False
        provided = payload.get("Token")
        if not provided:
            return False

        data = payload.copy()
        data.pop("Token", None)
        expected = self._token(data)

        return str(provided).strip().lower() == expected.lower()

    def init_payment(
        self,
        order_id: str,
        amount_kopeks: int,
        description: str,
        notification_url: str,
        success_url: str,
        fail_url: str,
        receipt: dict | None = None,
        data: dict | None = None,
        redirect_due_date: str | None = None,
        extra: dict | None = None,
    ):
        if not self.terminal_key or not self.password:
            raise ValueError("Не настроены TBANK_TERMINAL_KEY и TBANK_PASSWORD.")

        payload = {
            "TerminalKey": self.terminal_key,
            "Amount": amount_kopeks,
            "OrderId": order_id,
            "Description": description,
            "NotificationURL": notification_url,
            "SuccessURL": success_url,
            "FailURL": fail_url,
        }

        # Optional nested objects (do NOT participate in Token)
        if data:
            payload["DATA"] = data
        if receipt:
            payload["Receipt"] = receipt
        if redirect_due_date:
            payload["RedirectDueDate"] = redirect_due_date
        if extra:
            protected = {
                "Password",
                "Token",
                "TerminalKey",
                "Amount",
                "OrderId",
                "Description",
                "NotificationURL",
                "SuccessURL",
                "FailURL",
                "Receipt",
            }
            for key, value in extra.items():
                if key in protected:
                    continue
                if key == "DATA" and isinstance(value, dict):
                    base_data = payload.get("DATA") if isinstance(payload.get("DATA"), dict) else {}
                    payload["DATA"] = {**base_data, **value}
                    continue
                payload[key] = value

        payload["Token"] = self._token(payload)

        r = requests.post(f"{self.base_url}/Init", json=payload, timeout=15)
        try:
            body = r.json()
        except ValueError:
            text = (r.text or "").strip()
            short = text[:700] if text else ""
            if not r.ok:
                raise requests.HTTPError(
                    f"T-Bank Init HTTP {r.status_code}: {short or 'empty response'}",
                    response=r,
                )
            raise ValueError(f"T-Bank Init returned non-JSON response: {short or 'empty response'}")
        return body
