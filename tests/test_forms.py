import pytest

from pretix_bagnumbers.forms import BagNumberChangeForm, NumberRangeForm
from pretix_bagnumbers.models import BagNumber, ItemNumberConfig, NumberRange

from .conftest import make_order


@pytest.mark.django_db
def test_number_range_form_gueltig(event):
    form = NumberRangeForm(data={"name": "Kinder", "start": 100, "end": 199}, event=event)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_number_range_form_ende_kleiner_start(event):
    form = NumberRangeForm(data={"name": "Kinder", "start": 200, "end": 100}, event=event)
    assert not form.is_valid()
    assert any("Ende" in str(e) for e in form.non_field_errors())


@pytest.mark.django_db
def test_number_range_form_ueberlappung_wird_abgelehnt(event):
    NumberRange.objects.create(event=event, name="Bestehend", start=100, end=200)
    form = NumberRangeForm(data={"name": "Neu", "start": 150, "end": 250}, event=event)
    assert not form.is_valid()
    assert any("überschneidet" in str(e) for e in form.non_field_errors())


@pytest.mark.django_db
def test_number_range_form_ueberlappung_offener_kreis(event):
    NumberRange.objects.create(event=event, name="Offen", start=100, end=None)
    form = NumberRangeForm(data={"name": "Neu", "start": 200, "end": 300}, event=event)
    assert not form.is_valid()


@pytest.mark.django_db
def test_number_range_form_edit_keine_selbst_ueberlappung(event):
    rng = NumberRange.objects.create(event=event, name="Kinder", start=100, end=199)
    form = NumberRangeForm(
        data={"name": "Kinder", "start": 100, "end": 199},
        instance=rng,
        event=event,
    )
    assert form.is_valid(), form.errors


@pytest.fixture
def bagnumber(event):
    from pretix.base.models import Item
    rng = NumberRange.objects.create(event=event, name="Std", start=1)
    item = Item.objects.create(event=event, name="T", default_price=0)
    ItemNumberConfig.objects.create(item=item, number_range=rng)
    order = make_order(event, item, "BNX")
    pos = order.positions.first()
    return BagNumber.objects.create(event=event, position=pos, number_range=rng, number=1)


@pytest.mark.django_db
def test_bagnumber_change_form_gueltig(bagnumber):
    form = BagNumberChangeForm(data={"number": 42}, instance=bagnumber)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_bagnumber_change_form_duplikat_abgelehnt(event, bagnumber):
    from pretix.base.models import Item
    rng = bagnumber.number_range
    item2 = Item.objects.create(event=event, name="T2", default_price=0)
    order2 = make_order(event, item2, "BNY")
    pos2 = order2.positions.first()
    BagNumber.objects.create(event=event, position=pos2, number_range=rng, number=99)

    form = BagNumberChangeForm(data={"number": 99}, instance=bagnumber)
    assert not form.is_valid()
    assert "bereits vergeben" in str(form.errors)
