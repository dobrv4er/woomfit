import hashlib
import requests


class TBankClient:
    def __init__(self, terminal_key, password, is_test=True):
        self.terminal_key = terminal_key
        self.password = password
        self.base_url = (
            "https://rest-api-test.tinkoff.ru/v2"
            if is_test
            else "https://rest-api.tinkoff.ru/v2"
        )

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
            parts.append(str(v))

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
    ):
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

        payload["Token"] = self._token(payload)

        r = requests.post(f"{self.base_url}/Init", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
