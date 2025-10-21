from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0021_booking_stripe_invoice_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="StripePriceMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price_id", models.CharField(max_length=128, unique=True, db_index=True)),
                ("product_id", models.CharField(max_length=128, blank=True, null=True)),
                ("nickname", models.CharField(max_length=128, blank=True, null=True)),
                ("active", models.BooleanField(default=True, db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("service", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stripe_prices", to="core.service")),
            ],
            options={"ordering": ("price_id",)},
        ),
    ]
