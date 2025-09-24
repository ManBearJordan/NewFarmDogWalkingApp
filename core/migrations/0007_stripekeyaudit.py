# core/migrations/0007_stripekeyaudit.py
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import django.utils.timezone

class Migration(migrations.Migration):

    # If your repo's latest core migration has a different name,
    # replace ('core', '0006_client_user') below with the correct migration id.
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0006_client_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='StripeKeyAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('when', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('previous_mode', models.CharField(blank=True, max_length=32, null=True)),
                ('new_mode', models.CharField(blank=True, max_length=32, null=True)),
                ('previous_test_or_live', models.CharField(blank=True, max_length=16, null=True)),
                ('new_test_or_live', models.CharField(blank=True, max_length=16, null=True)),
                ('note', models.TextField(blank=True, default='')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-when'],
            },
        ),
    ]
