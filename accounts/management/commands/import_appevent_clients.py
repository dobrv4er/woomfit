import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.crypto import get_random_string

from accounts.models import User


def norm_phone(v: str) -> str:
    if not v:
        return ""
    digits = re.sub(r"\D+", "", v)
    # простая нормализация (под РФ): 8XXXXXXXXXX -> 7XXXXXXXXXX
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


def pick(row, *keys):
    # ищем значение по возможным заголовкам
    for k in keys:
        if k in row and row[k]:
            return str(row[k]).strip()
    return ""


class Command(BaseCommand):
    help = "Import clients exported from AppEvent (CSV). Creates/updates Users by phone/email."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to AppEvent CSV export")
        parser.add_argument("--dry-run", action="store_true", help="Parse only, do not write to DB")

    @transaction.atomic
    def handle(self, *args, **opts):
        csv_path = Path(opts["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"File not found: {csv_path}")

        # пробуем UTF-8, если не получится — часто в РФ бывает cp1251
        raw = csv_path.read_bytes()
        for enc in ("utf-8-sig", "utf-8", "cp1251"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                text = None
        if text is None:
            raise CommandError("Cannot decode file as utf-8/cp1251")

        # delimiter: в CSV иногда ; вместо ,
        sample = text[:2000]
        dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        reader = csv.DictReader(text.splitlines(), dialect=dialect)

        created = 0
        updated = 0
        skipped = 0

        for row in reader:
            full_name = pick(row, "Имя", "ФИО", "Name", "Full name")
            full_name = " ".join(full_name.split())
            phone = norm_phone(pick(row, "Телефон", "Номер телефона", "Phone"))
            email = pick(row, "Email", "E-mail", "Почта")

            if not (phone or email or full_name):
                skipped += 1
                continue

            # ключ поиска: телефон -> email
            user = None
            if phone:
                user = User.objects.filter(phone=phone).first()
            if user is None and email:
                user = User.objects.filter(email__iexact=email).first()

            if user is None:
                # username должен быть уникален
                base_username = email or (phone and f"user_{phone}") or f"user_{get_random_string(8)}"
                username = base_username
                i = 1
                while User.objects.filter(username=username).exists():
                    i += 1
                    username = f"{base_username}_{i}"

                if opts["dry_run"]:
                    created += 1
                    continue

                user = User.objects.create(
                    username=username,
                    email=email or "",
                    phone=phone or "",
                    full_name=full_name,
                    first_name="",
                    last_name="",
                )
                user.set_unusable_password()  # пароли из CRM перенести нельзя
                user.save()
                created += 1
            else:
                changed = False
                if email and (not user.email):
                    user.email = email
                    changed = True
                if phone and (not getattr(user, "phone", "")):
                    user.phone = phone
                    changed = True
                if full_name and (not user.full_name):
                    user.full_name = full_name
                    user.first_name = ""
                    user.last_name = ""
                    changed = True
                if changed and not opts["dry_run"]:
                    user.save()
                updated += 1 if changed else 0

        self.stdout.write(self.style.SUCCESS(
            f"Done. created={created}, updated={updated}, skipped={skipped}"
        ))
