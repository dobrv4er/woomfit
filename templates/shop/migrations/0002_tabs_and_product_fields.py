from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="section",
            field=models.CharField(
                choices=[
                    ("memberships", "Абонементы"),
                    ("personal", "Персональные"),
                    ("group", "Групповые"),
                    ("other", "Прочее"),
                ],
                db_index=True,
                default="group",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="subtitle",
            field=models.CharField(blank=True, default="", max_length=140),
        ),
        migrations.AddField(
            model_name="product",
            name="badge",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
        migrations.AddField(
            model_name="product",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="shop/"),
        ),
        migrations.AddField(
            model_name="product",
            name="sort",
            field=models.PositiveIntegerField(default=100),
        ),
    ]
