from django.conf import settings
from django.db import migrations, models


def infer_kind(apps, schema_editor):
    Session = apps.get_model("schedule", "Session")
    for s in Session.objects.all().only("id", "title"):
        title = (s.title or "").lower()
        if "аренд" in title:
            kind = "rent"
        elif "персон" in title:
            kind = "personal"
        else:
            kind = "group"
        Session.objects.filter(id=s.id).update(kind=kind)


class Migration(migrations.Migration):
    dependencies = [
        ("schedule", "0006_alter_session_options_alter_booking_unique_together_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="kind",
            field=models.CharField(
                choices=[("group", "Групповая"), ("personal", "Персональная"), ("rent", "Аренда")],
                default="group",
                max_length=16,
                db_index=True,
                verbose_name="Тип",
            ),
        ),
        migrations.AddField(
            model_name="session",
            name="client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="private_sessions",
                to=settings.AUTH_USER_MODEL,
                db_index=True,
                verbose_name="Клиент",
            ),
        ),
        migrations.RunPython(infer_kind, migrations.RunPython.noop),
    ]
