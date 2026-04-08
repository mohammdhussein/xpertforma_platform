from django.db import migrations, models


def split_existing_user_names(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.all().only("id", "first_name", "last_name"):
        full_name = (user.first_name or "").strip()
        parts = full_name.split()
        if not parts:
            first_name = ""
            last_name = ""
        elif len(parts) == 1:
            first_name = parts[0]
            last_name = ""
        else:
            first_name = parts[0]
            last_name = " ".join(parts[1:])

        if user.first_name != first_name or user.last_name != last_name:
            user.first_name = first_name
            user.last_name = last_name
            user.save(update_fields=["first_name", "last_name"])


def merge_existing_user_names(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.all().only("id", "first_name", "last_name"):
        merged_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
        if user.first_name != merged_name:
            user.first_name = merged_name
            user.save(update_fields=["first_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_coachprofile_phone_number"),
    ]

    operations = [
        migrations.RenameField(
            model_name="user",
            old_name="name",
            new_name="first_name",
        ),
        migrations.AlterField(
            model_name="user",
            name="first_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="user",
            name="last_name",
            field=models.CharField(blank=True, default="", max_length=120),
            preserve_default=False,
        ),
        migrations.RunPython(split_existing_user_names, merge_existing_user_names),
    ]
