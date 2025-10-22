from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_stripe_price_map"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Rename old AdminEvent to AdminTask
        migrations.RenameModel(
            old_name="AdminEvent",
            new_name="AdminTask",
        ),
        # Create new AdminEvent model for audit logging
        migrations.CreateModel(
            name="AdminEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("event_type", models.CharField(max_length=100, db_index=True)),
                ("message", models.TextField(blank=True, null=True)),
                ("context", models.JSONField(blank=True, null=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="admin_events", to=settings.AUTH_USER_MODEL)),
                ("booking", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="admin_events", to="core.booking")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
    ]
