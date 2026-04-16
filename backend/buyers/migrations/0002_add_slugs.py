from django.db import migrations, models
from django.utils.text import slugify


def backfill_slugs(apps, schema_editor):
    Buyer = apps.get_model('buyers', 'Buyer')
    BuyBox = apps.get_model('buyers', 'BuyBox')

    # Backfill buyer slugs, handling duplicates
    seen_slugs = set()
    for buyer in Buyer.objects.all():
        base = slugify(buyer.name) or f"buyer-{str(buyer.id)[:8]}"
        slug = base
        counter = 2
        while slug in seen_slugs:
            slug = f"{base}-{counter}"
            counter += 1
        seen_slugs.add(slug)
        buyer.slug = slug
        buyer.save(update_fields=['slug'])

    # Backfill buybox slugs
    for buybox in BuyBox.objects.select_related('buyer').all():
        base = slugify(buybox.asset_type[:80]) or f"buybox-{str(buybox.id)[:8]}"
        buybox.slug = base
        buybox.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('buyers', '0001_initial'),
    ]

    operations = [
        # Step 1: Add slug fields without unique constraint
        migrations.AddField(
            model_name='buyer',
            name='slug',
            field=models.SlugField(blank=True, default='', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='buybox',
            name='slug',
            field=models.SlugField(blank=True, default='', max_length=100),
            preserve_default=False,
        ),
        # Step 2: Backfill existing rows
        migrations.RunPython(backfill_slugs, migrations.RunPython.noop),
        # Step 3: Now add the constraints
        migrations.AlterField(
            model_name='buyer',
            name='slug',
            field=models.SlugField(blank=True, max_length=100, unique=True),
        ),
        migrations.AlterUniqueTogether(
            name='buybox',
            unique_together={('buyer', 'slug')},
        ),
    ]
