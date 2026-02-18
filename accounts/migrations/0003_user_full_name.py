from django.db import migrations, models


def forward_fill_full_name(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.all().iterator():
        if (user.full_name or "").strip():
            continue

        full_name = " ".join(
            part.strip() for part in [user.first_name, user.last_name] if part and part.strip()
        ).strip()
        if not full_name:
            continue

        User.objects.filter(pk=user.pk).update(
            full_name=full_name,
            first_name="",
            last_name="",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_user_options_alter_user_managers_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="full_name",
            field=models.CharField(blank=True, max_length=255, verbose_name="ФИО"),
        ),
        migrations.RunPython(forward_fill_full_name, migrations.RunPython.noop),
    ]
