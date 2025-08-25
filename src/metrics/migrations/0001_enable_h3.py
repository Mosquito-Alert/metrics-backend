from django.db import migrations


def create_h3_extension(apps, schema_editor):
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS h3;")


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.RunPython(create_h3_extension),
    ]
