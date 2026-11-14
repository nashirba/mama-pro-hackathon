from django.db import migrations, models


def set_roles_from_profiles(apps, schema_editor):
    """Accounts that already own a specialist or nanny profile take its category; everyone else stays a parent."""
    SpecialistProfile = apps.get_model("catalog", "SpecialistProfile")
    User = apps.get_model("accounts", "User")
    for category in ("specialist", "nanny"):
        user_ids = SpecialistProfile.objects.filter(category=category).values_list("user_id", flat=True)
        User.objects.filter(pk__in=user_ids).update(role=category)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_user_names_birth_date"),
        ("catalog", "0005_nannies"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[("parent", "Мама"), ("specialist", "Специалист"), ("nanny", "Няня")],
                default="parent",
                max_length=20,
            ),
        ),
        migrations.RunPython(set_roles_from_profiles, migrations.RunPython.noop),
    ]
