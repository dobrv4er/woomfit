from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
        ("shop", "0004_product_grant_kind_product_membership_days_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="fulfilled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="order_items",
                to="shop.product",
            ),
        ),
    ]
