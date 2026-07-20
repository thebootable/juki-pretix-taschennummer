from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('pretixbase', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='NumberRange',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=190)),
                ('start', models.PositiveIntegerField()),
                ('end', models.PositiveIntegerField(blank=True, null=True)),
                ('event', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='bagnumber_ranges',
                    to='pretixbase.event',
                )),
            ],
            options={
                'ordering': ('start',),
                'unique_together': {('event', 'name')},
            },
        ),
        migrations.CreateModel(
            name='ItemNumberConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='bagnumber_config',
                    to='pretixbase.item',
                )),
                ('number_range', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='pretix_bagnumbers.numberrange',
                )),
            ],
        ),
        migrations.CreateModel(
            name='BagNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveIntegerField()),
                ('event', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='bagnumbers',
                    to='pretixbase.event',
                )),
                ('number_range', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='numbers',
                    to='pretix_bagnumbers.numberrange',
                )),
                ('position', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='bagnumber',
                    to='pretixbase.orderposition',
                )),
            ],
            options={
                'ordering': ('number',),
            },
        ),
        migrations.AddConstraint(
            model_name='bagnumber',
            constraint=models.UniqueConstraint(
                fields=['event', 'number'],
                name='uniq_bagnumber_per_event',
            ),
        ),
    ]
