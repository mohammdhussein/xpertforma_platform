from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_playerprofile_age_playerprofile_foot_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="playerprofile",
            name="position_label",
        ),
    ]
