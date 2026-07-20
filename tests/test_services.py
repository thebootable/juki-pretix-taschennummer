"""
Tests für assign_number und release_number.

Voraussetzung: pytest-django, pretix im selben venv.
Ausführen:  pytest tests/
"""
import pytest
from django.core.exceptions import ValidationError

from pretix_bagnumbers.models import BagNumber, ItemNumberConfig, NumberRange
from pretix_bagnumbers.services import assign_number, release_number


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event(db):
    from pretix.base.models import Event, Organizer
    org = Organizer.objects.create(name="Test-Org", slug="testorg")
    return Event.objects.create(
        organizer=org,
        name="Testveranstaltung",
        slug="testev",
        date_from="2026-08-01",
        plugins="pretix_bagnumbers",
    )


@pytest.fixture
def number_range(event):
    return NumberRange.objects.create(event=event, name="Kinder", start=100, end=199)


@pytest.fixture
def item(event):
    from pretix.base.models import Item
    return Item.objects.create(event=event, name="Kinderticket", default_price=0)


@pytest.fixture
def item_with_range(item, number_range):
    ItemNumberConfig.objects.create(item=item, number_range=number_range)
    return item


@pytest.fixture
def order(event, item_with_range):
    from pretix.base.models import Order, OrderPosition
    o = Order.objects.create(
        event=event,
        code="TEST1",
        status=Order.STATUS_PENDING,
        datetime="2026-07-01T12:00:00Z",
        expires="2026-08-01T12:00:00Z",
        total=0,
        email="test@example.com",
    )
    OrderPosition.objects.create(order=o, item=item_with_range, price=0)
    return o


# ---------------------------------------------------------------------------
# assign_number
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assign_number_erste_nummer(order, number_range):
    pos = order.positions.first()
    result = assign_number(pos)
    assert result is not None
    assert result.number == 100


@pytest.mark.django_db
def test_assign_number_lueckenauffuellung(event, order, number_range):
    pos = order.positions.first()
    bn = assign_number(pos)
    assert bn.number == 100

    # Nummer 100 freigeben
    release_number(pos)

    # Zweite Bestellung – soll Nummer 100 wieder bekommen
    from pretix.base.models import Order, OrderPosition
    o2 = Order.objects.create(
        event=event, code="TEST2", status="n",
        datetime="2026-07-01T12:00:00Z", expires="2026-08-01T12:00:00Z",
        total=0, email="t2@example.com",
    )
    pos2 = OrderPosition.objects.create(order=o2, item=pos.item, price=0)
    bn2 = assign_number(pos2)
    assert bn2.number == 100


@pytest.mark.django_db
def test_assign_number_naechste_freie(event, order, number_range):
    """100 und 101 belegt → nächste ist 102."""
    from pretix.base.models import Order, OrderPosition
    pos = order.positions.first()
    assign_number(pos)  # → 100

    o2 = Order.objects.create(
        event=event, code="TEST2", status="n",
        datetime="2026-07-01T12:00:00Z", expires="2026-08-01T12:00:00Z",
        total=0, email="t2@example.com",
    )
    pos2 = OrderPosition.objects.create(order=o2, item=pos.item, price=0)
    assign_number(pos2)  # → 101

    o3 = Order.objects.create(
        event=event, code="TEST3", status="n",
        datetime="2026-07-01T12:00:00Z", expires="2026-08-01T12:00:00Z",
        total=0, email="t3@example.com",
    )
    pos3 = OrderPosition.objects.create(order=o3, item=pos.item, price=0)
    bn = assign_number(pos3)
    assert bn.number == 102


@pytest.mark.django_db
def test_assign_number_kreis_voll(event, number_range, item_with_range):
    """Wenn der Kreis voll ist, wird ValidationError ausgelöst."""
    number_range.end = 100  # nur eine Nummer
    number_range.save()

    from pretix.base.models import Order, OrderPosition
    o1 = Order.objects.create(
        event=event, code="T1", status="n",
        datetime="2026-07-01T12:00:00Z", expires="2026-08-01T12:00:00Z",
        total=0, email="a@b.de",
    )
    pos1 = OrderPosition.objects.create(order=o1, item=item_with_range, price=0)
    assign_number(pos1)  # → 100, erfolgreich

    o2 = Order.objects.create(
        event=event, code="T2", status="n",
        datetime="2026-07-01T12:00:00Z", expires="2026-08-01T12:00:00Z",
        total=0, email="c@d.de",
    )
    pos2 = OrderPosition.objects.create(order=o2, item=item_with_range, price=0)
    with pytest.raises(ValidationError):
        assign_number(pos2)


@pytest.mark.django_db
def test_assign_number_noop_wenn_schon_vergeben(order):
    """Zweiter Aufruf für dieselbe Position gibt die bestehende Nummer zurück."""
    pos = order.positions.first()
    bn1 = assign_number(pos)
    bn2 = assign_number(pos)
    assert bn1.number == bn2.number
    assert BagNumber.objects.filter(position=pos).count() == 1


@pytest.mark.django_db
def test_assign_number_noop_ohne_kreis(event):
    """Position ohne Nummernkreis-Konfiguration bekommt keine Nummer."""
    from pretix.base.models import Item, Order, OrderPosition
    item_ohne = Item.objects.create(event=event, name="Ohne", default_price=0)
    o = Order.objects.create(
        event=event, code="TX", status="n",
        datetime="2026-07-01T12:00:00Z", expires="2026-08-01T12:00:00Z",
        total=0, email="x@x.de",
    )
    pos = OrderPosition.objects.create(order=o, item=item_ohne, price=0)
    result = assign_number(pos)
    assert result is None
    assert not BagNumber.objects.filter(position=pos).exists()


# ---------------------------------------------------------------------------
# release_number
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_release_number(order):
    pos = order.positions.first()
    assign_number(pos)
    assert BagNumber.objects.filter(position=pos).exists()
    release_number(pos)
    assert not BagNumber.objects.filter(position=pos).exists()


@pytest.mark.django_db
def test_release_number_noop_ohne_nummer(order):
    """release_number auf einer Position ohne Nummer wirft keinen Fehler."""
    pos = order.positions.first()
    release_number(pos)  # kein Fehler erwartet
