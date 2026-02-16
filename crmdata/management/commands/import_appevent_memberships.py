import re
import hashlib
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.crypto import get_random_string

import xlrd

from accounts.models import User
from crmdata.models import Membership


def norm_phone(v: str) -> str:
    if not v:
        return ""
    digits = re.sub(r"\D+", "", str(v))
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


def split_name(full: str):
    full = (full or "").strip()
    if not full:
        return "", ""
    parts = full.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def parse_date(s: str):
    s = (s or "").strip()
    if not s:
        return None
    # в вашем файле даты идут как '2025-12-13'
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def parse_dt(s: str):
    s = (s or "").strip()
    if not s:
        return None
    # в вашем файле datetime идет как '2023-11-13 11:07:56'
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def parse_left_total(raw: str):
    """
    'Состав (остаток)' часто типа '... 7/8' где 7 = осталось, 8 = всего.
    """
    if not raw:
        return (None, None, None)
    s = str(raw)
    m = re.search(r"(\d+)\s*/\s*(\d+)", s)
    if m:
        left = int(m.group(1))
        total = int(m.group(2))
        used = max(0, total - left)
        return total, left, used

    # если нет дроби, но есть число (например "16 занятий")
    m2 = re.search(r"(\d+)", s)
    if m2:
        total = int(m2.group(1))
        return total, None, None

    return (None, None, None)


class Command(BaseCommand):
    help = "Import AppEvent memberships from XLS (memberships.xls)."

    def add_arguments(self, parser):
        parser.add_argument("xls_path", type=str)
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        xls_path = Path(opts["xls_path"])
        if not xls_path.exists():
            raise CommandError(f"File not found: {xls_path}")

        book = xlrd.open_workbook(str(xls_path))
        sheet = book.sheet_by_index(0)

        headers = [str(sheet.cell_value(0, c)).strip() for c in range(sheet.ncols)]
        idx = {h: i for i, h in enumerate(headers)}

        required = [
            "Абонемент", "Статус абонемента", "Статус оплаты",
            "Состав (остаток)", "Клиент", "Номер телефона",
            "Действителен до", "Оформлен"
        ]
        missing = [h for h in required if h not in idx]
        if missing:
            raise CommandError(f"Missing columns: {missing}. Found: {headers}")

        created = 0
        updated = 0
        skipped = 0

        for r in range(1, sheet.nrows):
            title = str(sheet.cell_value(r, idx["Абонемент"])).strip()
            m_status = str(sheet.cell_value(r, idx["Статус абонемента"])).strip()
            p_status = str(sheet.cell_value(r, idx["Статус оплаты"])).strip()
            comp = str(sheet.cell_value(r, idx["Состав (остаток)"])).strip()
            client = str(sheet.cell_value(r, idx["Клиент"])).strip()
            phone = norm_phone(sheet.cell_value(r, idx["Номер телефона"]))
            valid_to = parse_date(str(sheet.cell_value(r, idx["Действителен до"])).strip())
            purchased_at = parse_dt(str(sheet.cell_value(r, idx["Оформлен"])).strip())

            if not title and not phone:
                skipped += 1
                continue

            # Найти/создать пользователя по телефону
            user = None
            if phone:
                user = User.objects.filter(phone=phone).first()

            if user is None:
                first, last = split_name(client)
                base_username = f"user_{phone}" if phone else f"user_{get_random_string(8)}"
                username = base_username
                k = 1
                while User.objects.filter(username=username).exists():
                    k += 1
                    username = f"{base_username}_{k}"

                if opts["dry_run"]:
                    user = None
                else:
                    user = User.objects.create(
                        username=username,
                        phone=phone or "",
                        first_name=first,
                        last_name=last,
                    )
                    user.set_unusable_password()
                    user.save()

            total, left, used = parse_left_total(comp)

            # чтобы не плодить дублей, делаем стабильный ключ
            raw_key = f"{phone}|{title}|{purchased_at}|{valid_to}|{comp}|{m_status}|{p_status}"
            ext = hashlib.sha1(raw_key.encode("utf-8")).hexdigest()[:16]

            if opts["dry_run"]:
                created += 1
                continue

            obj, is_created = Membership.objects.update_or_create(
                user=user,
                title=title,
                purchased_at=purchased_at,
                defaults={
                    "membership_status": m_status,
                    "payment_status": p_status,
                    "composition_raw": comp,
                    "total_visits": total,
                    "left_visits": left,
                    "used_visits": used,
                    "valid_to": valid_to,
                }
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        self.stdout.write(self.style.SUCCESS(
            f"OK: created={created}, updated={updated}, skipped={skipped}"
        ))
