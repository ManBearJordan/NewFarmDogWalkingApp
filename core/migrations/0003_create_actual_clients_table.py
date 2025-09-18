# Generated manually to create clients table
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_create_clients_table'),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(200) NOT NULL,
                email VARCHAR(254),
                phone VARCHAR(20),
                address TEXT,
                stripe_customer_id VARCHAR(100) UNIQUE,
                credit_cents INTEGER NOT NULL DEFAULT 0,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                acquisition_date DATETIME NOT NULL,
                last_service_date DATETIME,
                total_revenue_cents INTEGER NOT NULL DEFAULT 0,
                service_count INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            """,
            "DROP TABLE IF EXISTS clients;"
        )
    ]