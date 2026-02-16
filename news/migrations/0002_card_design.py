from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("news", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="newspost",
            name="card_title",
            field=models.CharField(blank=True, max_length=30, verbose_name="Текст на карточке"),
        ),
        migrations.AddField(
            model_name="newspost",
            name="font_family",
            field=models.CharField(choices=[("system", "Системный"), ("inter", "Inter"), ("montserrat", "Montserrat"), ("nunito", "Nunito"), ("playfair", "Playfair Display")], default="system", max_length=16, verbose_name="Шрифт карточки"),
        ),
        migrations.AddField(
            model_name="newspost",
            name="overlay_color",
            field=models.CharField(default="#000000", max_length=7, verbose_name="Цвет подложки (HEX)"),
        ),
        migrations.AddField(
            model_name="newspost",
            name="overlay_opacity",
            field=models.PositiveIntegerField(default=65, verbose_name="Прозрачность подложки (%)"),
        ),
        migrations.AddField(
            model_name="newspost",
            name="overlay_style",
            field=models.CharField(choices=[("gradient", "Градиент снизу"), ("solid", "Сплошная подложка")], default="gradient", max_length=16, verbose_name="Подложка"),
        ),
        migrations.AddField(
            model_name="newspost",
            name="text_color",
            field=models.CharField(default="#FFFFFF", max_length=7, verbose_name="Цвет текста (HEX)"),
        ),
    ]
