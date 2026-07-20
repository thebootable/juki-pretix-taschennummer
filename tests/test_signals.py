import pytest

from pretix_bagnumbers.models import BagNumber, ItemNumberConfig, NumberRange
from pretix_bagnumbers.signals import (
    copy_event_data,
    on_order_canceled,
    on_order_changed,
    on_order_gracefully_delete,
    on_order_placed,
    on_order_reactivated,
)

from .conftest import make_order


@pytest.fixture
def number_range(event):
    return NumberRange.objects.create(event=event, name="Standard", start=1)


@pytest.fixture
def item(event, number_range):
    from pretix.base.models import Item
    it = Item.objects.create(event=event, name="Ticket", default_price=0)
    ItemNumberConfig.objects.create(item=it, number_range=number_range)
    return it


@pytest.mark.django_db
def test_on_order_placed_vergibt_nummer(event, item):
    order = make_order(event, item, "P1")
    on_order_placed(sender=event, order=order)
    assert BagNumber.objects.filter(event=event).count() == 1


@pytest.mark.django_db
def test_on_order_canceled_gibt_frei(event, item):
    order = make_order(event, item, "C1")
    on_order_placed(sender=event, order=order)
    on_order_canceled(sender=event, order=order)
    assert not BagNumber.objects.filter(event=event).exists()


@pytest.mark.django_db
def test_on_order_reactivated_vergibt_neue_nummer(event, item):
    order = make_order(event, item, "R1")
    on_order_placed(sender=event, order=order)
    alte_nummer = BagNumber.objects.get(event=event).number

    on_order_canceled(sender=event, order=order)

    order2 = make_order(event, item, "R2")
    on_order_placed(sender=event, order=order2)

    on_order_reactivated(sender=event, order=order)
    pos1 = order.positions.first()
    neue_nummer = BagNumber.objects.get(position=pos1).number
    assert BagNumber.objects.filter(event=event).count() == 2
    assert neue_nummer != alte_nummer


@pytest.mark.django_db
def test_on_order_changed_teilstorno_gibt_frei(event, item):
    order = make_order(event, item, "CH1")
    on_order_placed(sender=event, order=order)
    assert BagNumber.objects.filter(event=event).count() == 1

    pos = order.positions.first()
    pos.canceled = True
    pos.save()

    on_order_changed(sender=event, order=order)
    assert not BagNumber.objects.filter(event=event).exists()


@pytest.mark.django_db
def test_on_order_gracefully_delete(event, item):
    order = make_order(event, item, "GD1")
    on_order_placed(sender=event, order=order)
    on_order_gracefully_delete(sender=event, order=order)
    assert not BagNumber.objects.filter(event=event).exists()


@pytest.mark.django_db
def test_copy_event_data_kopiert_kreise_nicht_nummern(event, item, number_range):
    from pretix.base.models import Event, Item

    order = make_order(event, item, "CP1")
    on_order_placed(sender=event, order=order)
    assert BagNumber.objects.filter(event=event).count() == 1

    klon = Event.objects.create(
        organizer=event.organizer, name="Klon", slug="klon",
        date_from="2027-08-01", plugins="pretix_bagnumbers",
    )
    klon_item = Item.objects.create(event=klon, name="Ticket", default_price=0)
    item_map = {item.pk: klon_item}

    copy_event_data(sender=klon, other=event, item_map=item_map)

    assert NumberRange.objects.filter(event=klon).count() == 1
    assert BagNumber.objects.filter(event=klon).count() == 0
    assert ItemNumberConfig.objects.filter(item=klon_item).exists()
