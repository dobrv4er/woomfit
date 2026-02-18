from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import Any
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Session


@dataclass
class Block:
    id: int
    kind: str
    title: str
    trainer: str
    location: str
    start_at: datetime
    end_at: datetime
    duration_min: int
    top_px: int
    height_px: int
    hhmm: str
    end_hhmm: str
    edit_url: str


def _safe_int(v: str | None, default: int) -> int:
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _parse_day(s: str | None, tz) -> datetime:
    if not s:
        return timezone.localdate()
    try:
        # expected YYYY-MM-DD
        d = datetime.strptime(s, "%Y-%m-%d").date()
        return d
    except ValueError:
        return timezone.localdate()


def _combine_local(day, hhmm: str, tz) -> datetime:
    # hhmm expected HH:MM
    hh, mm = hhmm.split(":")
    dt = datetime.combine(day, time(int(hh), int(mm)))
    return timezone.make_aware(dt, tz)


def _fmt_hhmm(dt: datetime, tz) -> str:
    return timezone.localtime(dt, tz).strftime("%H:%M")


def _normalize_loc(s: str) -> str:
    return (s or "").strip().lower().replace("ё", "е").replace(" ", "")


def _compact_ws(s: str | None) -> str:
    return " ".join((s or "").split()).strip()


def _location_norm_aliases(raw_loc: str) -> set[str]:
    """
    Допускаем частую опечатку 8б/86, чтобы не плодить "ложные" адреса.
    """
    norm = _normalize_loc(raw_loc)
    if not norm:
        return set()

    aliases = {norm}
    if norm.endswith("8б"):
        aliases.add(norm[:-2] + "86")
    if norm.endswith("86"):
        aliases.add(norm[:-2] + "8б")
    return aliases


def _dedupe_locations(raw_locations) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for loc in raw_locations or []:
        c = _compact_ws(str(loc))
        if not c:
            continue
        n = _normalize_loc(c)
        if n in seen:
            continue
        seen.add(n)
        cleaned.append(c)
    return cleaned


def _canonical_location(raw_loc: str | None, known_locations: list[str]) -> str:
    raw_clean = _compact_ws(raw_loc)
    if not raw_clean:
        return ""

    by_norm: dict[str, str] = {}
    for loc in known_locations:
        c = _compact_ws(loc)
        if not c:
            continue
        by_norm.setdefault(_normalize_loc(c), c)

    for alias in _location_norm_aliases(raw_clean):
        canonical = by_norm.get(alias)
        if canonical:
            return canonical
    return raw_clean


@staff_member_required
def planning(request: HttpRequest):
    tz = timezone.get_current_timezone()

    # day / range
    day = _parse_day(request.GET.get("day"), tz)
    grid_start_h = _safe_int(request.GET.get("from"), 8)
    grid_end_h = _safe_int(request.GET.get("to"), 22)
    grid_start_h = max(0, min(23, grid_start_h))
    grid_end_h = max(1, min(24, grid_end_h))
    if grid_end_h <= grid_start_h:
        grid_end_h = min(24, grid_start_h + 1)

    grid_start = _combine_local(day, f"{grid_start_h:02d}:00", tz)
    grid_end = _combine_local(day, f"{grid_end_h:02d}:00", tz)

    # constants: 60 minutes = 72px
    px_per_min = 72 / 60
    grid_height_px = int(((grid_end - grid_start).total_seconds() // 60) * px_per_min)

    # ✅ 10-минутные слоты для кликов (без вычислений по пикселям на фронте)
    slot_step_min = 10
    slot_height_px = int(slot_step_min * px_per_min)

    slots = []
    total_minutes = int((grid_end - grid_start).total_seconds() // 60)
    for m in range(0, total_minutes, slot_step_min):
        t = grid_start + timedelta(minutes=m)
        slots.append({
            "start": timezone.localtime(t, tz).strftime("%H:%M"),
            "top_px": int(m * px_per_min),
        })

    # locations list: from settings, fallback from existing sessions for that day
    from django.conf import settings

    raw_locations = getattr(settings, "WOOMFIT_LOCATIONS", None) or []
    locations = _dedupe_locations(raw_locations)

    # if settings empty, derive from db
    if not locations:
        qs_loc = (
            Session.objects
            .filter(start_at__gte=grid_start, start_at__lt=grid_end)
            .values_list("location", flat=True)
            .distinct()
        )
        locations = _dedupe_locations(qs_loc)

    # query sessions for that window
    qs = (
        Session.objects
        .select_related("trainer")
        .filter(start_at__gte=grid_start, start_at__lt=grid_end)
        .order_by("start_at")
    )

    # group by normalized location
    col_map: dict[str, list[Block]] = {loc: [] for loc in locations}
    # also accept sessions whose loc not in configured list
    extra_locs: dict[str, list[Block]] = {}

    for s in qs:
        start_local = timezone.localtime(s.start_at, tz)
        end_local = start_local + timedelta(minutes=s.duration_min or 0)
        mins_from_start = int((start_local - timezone.localtime(grid_start, tz)).total_seconds() // 60)

        top_px = int(mins_from_start * px_per_min)
        height_px = int((s.duration_min or 0) * px_per_min)

        canonical_loc = _canonical_location(s.location, locations)
        b = Block(
            id=s.id,
            kind=s.kind,
            title=s.title,
            trainer=getattr(s.trainer, "name", "") if s.trainer_id else "",
            location=canonical_loc or "",
            start_at=start_local,
            end_at=end_local,
            duration_min=s.duration_min or 0,
            top_px=top_px,
            height_px=max(18, height_px),
            hhmm=start_local.strftime("%H:%M"),
            end_hhmm=end_local.strftime("%H:%M"),
            edit_url=reverse("admin:schedule_session_change", args=[s.id]),
        )

        placed = False
        for loc in locations:
            if _normalize_loc(loc) == _normalize_loc(b.location):
                col_map[loc].append(b)
                placed = True
                break
        if not placed:
            extra_locs.setdefault(b.location or "Без адреса", []).append(b)

    # merge extra columns at the end
    for loc, blocks in extra_locs.items():
        col_map[loc] = blocks

    # hours labels
    hours = []
    cur = grid_start
    while cur < grid_end:
        hours.append(cur)
        cur += timedelta(hours=1)

    ctx: dict[str, Any] = {
        "day": day,
        "grid_start_h": grid_start_h,
        "grid_end_h": grid_end_h,
        "grid_height_px": grid_height_px,
        "px_per_min": px_per_min,
        "hours": hours,
        "columns": col_map,
        "admin_add_url": reverse("admin:schedule_session_add"),
        "move_url": reverse("crm_planning_move"),


        "slots": slots,
        "slot_height_px": slot_height_px,
        "slot_step_min": slot_step_min,
    }
    return render(request, "crm/planning.html", ctx)


@staff_member_required
@require_POST
def session_move(request: HttpRequest):
    # expects json: {session_id, day, start, loc}
    import json

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "bad_json"}, status=400)

    session_id = payload.get("session_id")
    day = payload.get("day")
    start = payload.get("start")
    loc = payload.get("loc")

    if not session_id or not day or not start or not loc:
        return JsonResponse({"ok": False, "error": "missing_fields"}, status=400)

    tz = timezone.get_current_timezone()

    try:
        d = datetime.strptime(day, "%Y-%m-%d").date()
        hh, mm = start.split(":")
        new_dt = timezone.make_aware(datetime.combine(d, time(int(hh), int(mm))), tz)
    except Exception:
        return JsonResponse({"ok": False, "error": "bad_datetime"}, status=400)

    from django.conf import settings

    known_locations = _dedupe_locations(getattr(settings, "WOOMFIT_LOCATIONS", None) or [])
    canonical_loc = _canonical_location(loc, known_locations) or _compact_ws(loc)

    s = get_object_or_404(Session, pk=session_id)
    s.start_at = new_dt
    s.location = canonical_loc
    try:
        s.full_clean()
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": "validation", "messages": exc.messages}, status=400)
    s.save(update_fields=["start_at", "location"])

    return JsonResponse({"ok": True})
move_session = session_move


def _week_start(d):
    """Понедельник 00:00 выбранной даты (локальная зона)."""
    return d - timedelta(days=d.weekday())


def _overlaps(start_a, dur_a_min, start_b, dur_b_min):
    end_a = start_a + timedelta(minutes=dur_a_min)
    end_b = start_b + timedelta(minutes=dur_b_min)
    return start_a < end_b and start_b < end_a


@staff_member_required
@require_POST
def repeat_week(request):
    """
    Копирует все Session из недели source -> week target.
    - сохраняет время, длительность, зал, тренера, title, capacity
    - опционально сдвигает время на shift_min минут
    - пропускает конфликты по location и trainer (чтобы не было пересечений)
    """
    src_day = request.POST.get("src_day")
    dst_day = request.POST.get("dst_day")
    shift_min = request.POST.get("shift_min", "0")

    try:
        shift_min = int(shift_min)
    except ValueError:
        shift_min = 0

    if not src_day or not dst_day:
        messages.error(request, "Нужно выбрать неделю-источник и неделю-назначение")
        return redirect("crm_planning")

    tz = timezone.get_current_timezone()

    try:
        src_date = datetime.strptime(src_day, "%Y-%m-%d").date()
        dst_date = datetime.strptime(dst_day, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Неверный формат даты")
        return redirect("crm_planning")

    src_monday = _week_start(src_date)
    dst_monday = _week_start(dst_date)

    src_start = timezone.make_aware(datetime.combine(src_monday, datetime.min.time()), tz)
    src_end = src_start + timedelta(days=7)

    dst_start = timezone.make_aware(datetime.combine(dst_monday, datetime.min.time()), tz)
    dst_end = dst_start + timedelta(days=7)

    from .models import Session
    from django.conf import settings

    known_locations = _dedupe_locations(getattr(settings, "WOOMFIT_LOCATIONS", None) or [])

    src_sessions = (
        Session.objects
        .select_related("trainer")
        .filter(start_at__gte=src_start, start_at__lt=src_end)
        .order_by("start_at")
    )

    # заранее загрузим всё что уже есть в целевой неделе — чтобы проверять конфликты
    existing_dst = list(
        Session.objects
        .filter(start_at__gte=dst_start, start_at__lt=dst_end)
        .values("start_at", "duration_min", "location", "trainer_id")
    )

    created = 0
    skipped = 0

    # также учитываем конфликты между тем, что мы создаём в ходе копирования
    newly_planned = []

    def has_conflict(new_start, new_dur, new_loc, new_trainer_id):
        # конфликт по залу или по тренеру
        for s in existing_dst:
            if (s["location"] == new_loc) or (s["trainer_id"] and s["trainer_id"] == new_trainer_id):
                if _overlaps(new_start, new_dur, s["start_at"], s["duration_min"] or 0):
                    return True
        for s in newly_planned:
            if (s["location"] == new_loc) or (s["trainer_id"] and s["trainer_id"] == new_trainer_id):
                if _overlaps(new_start, new_dur, s["start_at"], s["duration_min"] or 0):
                    return True
        return False

    with transaction.atomic():
        for s in src_sessions:
            # сдвиг по дням недели + shift_min по времени
            delta_days = (timezone.localtime(s.start_at, tz).date() - src_monday).days
            base = dst_start + timedelta(days=delta_days)

            src_local = timezone.localtime(s.start_at, tz)
            # переносим время из src_local в base-день
            new_naive = datetime.combine(base.date(), src_local.time()) + timedelta(minutes=shift_min)
            new_start = timezone.make_aware(new_naive, tz)

            new_dur = int(s.duration_min or 0)
            new_loc = _canonical_location(s.location, known_locations) or ""
            new_trainer_id = s.trainer_id

            # защита: кратность 10 минутам (если хочешь строго)
            # если не кратно — округлим вниз к ближайшим 10
            mins_total = new_start.hour * 60 + new_start.minute
            mins_rounded = (mins_total // 10) * 10
            if mins_rounded != mins_total:
                hh = mins_rounded // 60
                mm = mins_rounded % 60
                new_start = new_start.replace(hour=hh, minute=mm, second=0, microsecond=0)

            # пропускаем всё, что выпало за неделю назначения (из-за shift)
            if not (dst_start <= new_start < dst_end):
                skipped += 1
                continue

            if has_conflict(new_start, new_dur, new_loc, new_trainer_id):
                skipped += 1
                continue

            # создаём копию
            Session.objects.create(
                title=s.title,
                kind=s.kind,
                workout=s.workout,
                client=s.client,
                start_at=new_start,
                duration_min=s.duration_min,
                location=new_loc,
                trainer_id=s.trainer_id,
                capacity=s.capacity,
            )
            newly_planned.append({
                "start_at": new_start,
                "duration_min": new_dur,
                "location": new_loc,
                "trainer_id": new_trainer_id,
            })
            created += 1

    if created:
        messages.success(request, f"Готово: создано {created} занятий. Пропущено из-за конфликтов/границ недели: {skipped}.")
    else:
        messages.warning(request, f"Ничего не создано. Пропущено: {skipped} (конфликты или всё выпало из недели).")

    # возвращаемся на planning недели назначения
    return redirect(f"/admin/planning/?day={dst_monday.strftime('%Y-%m-%d')}&from=8&to=22")
