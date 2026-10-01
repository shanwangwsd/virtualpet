from django.db import migrations, models


def normalize_fitness(apps, schema_editor):
    Pet = apps.get_model('core', 'Pet')
    pets = Pet.objects.using(schema_editor.connection.alias)
    pets.filter(fitness__lt=0).update(fitness=0)
    pets.filter(fitness__gt=100).update(fitness=100)
    pets.filter(fitness=0).exclude(state='dead').update(
        state='dead', died_at=models.F('updated_at'), rest_at=None,
    )


class Migration(migrations.Migration):
    dependencies = [('core', '0006_unified_pet')]
    operations = [
        migrations.RunPython(normalize_fitness, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='pet',
            constraint=models.CheckConstraint(
                condition=models.Q(fitness__gte=0, fitness__lte=100),
                name='pet_fitness_range',
            ),
        ),
    ]
