from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("training", "0009_session_lifecycle_attendance"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                'CREATE EXTENSION IF NOT EXISTS pgcrypto;',
                'ALTER TABLE training_sessionattendance '
                'ALTER COLUMN id SET DEFAULT gen_random_uuid();',
            ],
            reverse_sql=[
                'ALTER TABLE training_sessionattendance '
                'ALTER COLUMN id DROP DEFAULT;',
            ],
        ),
    ]
