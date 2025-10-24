from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0023_admin_event_audit"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceWindow",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=100)),
                ("active", models.BooleanField(default=True)),
                ("weekday", models.SmallIntegerField(
                    choices=[
                        (-1, "All days"),
                        (0, "Mon"),
                        (1, "Tue"),
                        (2, "Wed"),
                        (3, "Thu"),
                        (4, "Fri"),
                        (5, "Sat"),
                        (6, "Sun")
                    ],
                    default=-1
                )),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("block_in_portal", models.BooleanField(default=True)),
                ("warn_in_admin", models.BooleanField(default=True)),
                ("max_concurrent", models.PositiveIntegerField(
                    null=True,
                    blank=True,
                    help_text="Optional. 0 or blank disables capacity check."
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("allowed_services", models.ManyToManyField(
                    to="core.Service",
                    blank=True,
                    related_name="allowed_windows"
                )),
            ],
            options={"ordering": ("weekday", "start_time", "title")},
        ),
    ]
