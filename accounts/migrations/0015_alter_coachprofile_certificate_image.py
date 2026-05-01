from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0014_playerprofile_expected_return_date_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="coachprofile",
            name="certificate_image",
            field=models.ImageField(
                blank=True,
                max_length=500,
                null=True,
                upload_to="coach_certificates/",
            ),
        ),
    ]
