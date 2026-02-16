from django.db import migrations, models


def create_workouts_from_titles(apps, schema_editor):
    Session = apps.get_model("schedule", "Session")
    Workout = apps.get_model("schedule", "Workout")

    cache = {}
    for s in Session.objects.all().iterator():
        title = (s.title or "").strip() or "Тренировка"
        w = cache.get(title)
        if not w:
            w = Workout.objects.create(
                name=title,
                default_duration_min=getattr(s, "duration_min", 50) or 50,
                default_capacity=getattr(s, "capacity", 20) or 20,
            )
            cache[title] = w
        s.workout_id = w.id
        s.save(update_fields=["workout"])


class Migration(migrations.Migration):

    dependencies = [
        ("schedule", "0008_payment_intent_and_invite"),
    ]

    operations = [
        migrations.CreateModel(
            name="Workout",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160, verbose_name="Название")),
                ("level", models.CharField(blank=True, default="", max_length=80, verbose_name="Уровень")),
                ("description", models.TextField(blank=True, default="", verbose_name="Описание")),
                ("what_to_bring", models.TextField(blank=True, default="", verbose_name="Что взять с собой")),
                ("image", models.ImageField(blank=True, null=True, upload_to="workouts/", verbose_name="Картинка")),
                ("default_duration_min", models.PositiveIntegerField(default=50, verbose_name="Длительность по умолчанию, мин")),
                ("default_capacity", models.PositiveIntegerField(default=20, verbose_name="Вместимость по умолчанию")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Тренировка (шаблон)",
                "verbose_name_plural": "Тренировки (шаблоны)",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="session",
            name="workout",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name="sessions",
                to="schedule.workout",
                verbose_name="Шаблон тренировки",
                db_index=True,
            ),
        ),
        migrations.RunPython(create_workouts_from_titles, migrations.RunPython.noop),
    ]
