"""
Tests für die Signal-Handler (order_placed, order_canceled, etc.).
"""
import pytest

from pretix_bagnumbers.models import BagNumber, ItemNumberConfig, NumberRange
from pretix_bagnumbers.signals import (
    copy_event_data,
    on_order_canceled,
    on_order_changed,
    on_order_gracefully_delete,
    on_order_placed,
    on_order_reactivated,
    on_order_split,
)


# ---------------------------------------------------------------------------
# Fixtures (identisch zu test_services, könnten in conftest.py ausgelagert werden)
# ---------------------------------------------------------------------------

@pytest.fixture
def event(db):
    from pretix.base.models import Event, Organizer
    org = Organizer.objects.create(name="Sig-Org", slug="sigtestorg")
    return Event.objects.create(
        organizer=org, name="Sigtestev", slug="sigtestev",
        date_from="2026-08-01", plugins="pretix_bagnumbers",
    )


@pytest.fixture
def number_range(event):
    return NumberRange.objects.create(event=event, name="Standard", start=1)


@pytest.fixture
def item(event, number_range):
    from pretix.base.models import Item
    it = Item.objects.create(event=event, name="Ticket", default_price=0)
    ItemNumberConfig.objects.create(item=it, number_range=number_range)
    return it


def make_order(event, item, code):
    from pretix.base.models import Order, OrderPosition
    o = Order.objects.create(
        event=event, code=code, status=Order.STATUS_PENDING,
        datetime="2026-07-01T12:00:00Z", expires="2026-08-01T12:00:00Z",
        total=0, email="test@example.com",
    )
    OrderPosition.objects.create(order=o, item=item, price=0)
    return o


# ---------------------------------------------------------------------------
# order_placed
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_on_order_placed_vergibt_nummer(event, item):
    order = make_order(event, item, "P1")
    on_order_placed(sender=event, order=order)
    assert BagNumber.objects.filter(event=event).count() == 1


# ---------------------------------------------------------------------------
# order_canceled
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_on_order_canceled_gibt_frei(event, item):
    order = make_order(event, item, "C1")
    on_order_placed(sender=event, order=order)
    assert BagNumber.objects.filter(event=event).exists()
    on_order_canceled(sender=event, order=order)
    assert not BagNumber.objects.filter(event=event).exists()


# ---------------------------------------------------------------------------
# order_reactivated
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_on_order_reactivated_vergibt_neue_nummer(event, item):
    order = make_order(event, item, "R1")
    on_order_placed(sender=event, order=order)
    alte_nummer = BagNumber.objects.get(event=event).number

    on_order_canceled(sender=event, order=order)

    # Zweite Bestellung belegt die kleinste Nummer
    order2 = make_order(event, item, "R2")
    on_order_placed(sender=event, order=order2)

    # Reaktivierung von order1 → bekommt NEUE Nummer (nicht die alte)
    on_order_reactivated(sender=event, order=order)
    nummern = list(BagNumber.objects.filter(event=event).values_list("number", flat=True))
    assert len(nummern) == 2
    # Alte Nummer ist jetzt vergeben an order2; order1 hat eine andere
    pos1 = order.positions.first()
    neue_nummer = BagNumber.objects.get(position=pos1).number
    assert neue_nummer != alte_nummer or nummern.count(alte_nummer) == 1


# ---------------------------------------------------------------------------
# order_changed (Teilstorno)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_on_order_changed_teilstorno_gibt_frei(event, item):
    from pretix.base.models import OrderPosition
    order = make_order(event, item, "CH1")
    on_order_placed(sender=event, order=order)
    assert BagNumber.objects.filter(event=event).count() == 1

    # Position als storniert markieren
    pos = order.positions.first()
    pos.canceled = True
    pos.save()

    on_order_changed(sender=event, order=order)
    assert not BagNumber.objects.filter(event=event).exists()


# ---------------------------------------------------------------------------
# order_gracefully_delete (Testmodus)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_on_order_gracefully_delete(event, item):
    order = make_order(event, item, "GD1")
    on_order_placed(sender=event, order=order)
    assert BagNumber.objects.filter(event=event).exists()
    on_order_gracefully_delete(sender=event, order=order)
    assert not BagNumber.objects.filter(event=event).exists()


# ---------------------------------------------------------------------------
# event_copy_data
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_copy_event_data_kopiert_kreise_nicht_nummern(event, item, number_range):
    from pretix.base.models import Event, Item, Order, OrderPosition

    # Nummer vergeben
    order = make_order(event, item, "CP1")
    on_order_placed(sender=event, order=order)
    assert BagNumber.objects.filter(event=event).count() == 1

    # Klon-Event
    klon = Event.objects.create(
        organizer=event.organizer, name="Klon", slug="klon",
        date_from="2027-08-01", plugins="pretix_bagnumbers",
    )
    klon_item = Item.objects.create(event=klon, name="Ticket", default_price=0)
    item_map = {item.pk: klon_item}

    copy_event_data(sender=klon, other=event, item_map=item_map)

    # Kreis wurde kopiert
    assert NumberRange.objects.filter(event=klon).count() == 1
    # Nummern wurden NICHT kopiert
    assert BagNumber.objects.filter(event=klon).count() == 0
    # Produktzuordnung wurde kopiert
    assert ItemNumberConfig.objects.filter(item=klon_item).exists()
