import pytest
from django.core.exceptions import ValidationError

from pretix_bagnumbers.models import BagNumber, ItemNumberConfig, NumberRange
from pretix_bagnumbers.services import assign_number, release_number

from .conftest import make_order


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
    return make_order(event, item_with_range, "TEST1")


@pytest.mark.django_db
def test_assign_number_erste_nummer(order, number_range):
    pos = order.positions.first()
    result = assign_number(pos)
    assert result is not None
    assert result.number == 100


@pytest.mark.django_db
def test_assign_number_lueckenauffuellung(event, order, number_range, item_with_range):
    pos = order.positions.first()
    assign_number(pos)
    release_number(pos)

    order2 = make_order(event, item_with_range, "TEST2")
    bn2 = assign_number(order2.positions.first())
    assert bn2.number == 100


@pytest.mark.django_db
def test_assign_number_naechste_freie(event, order, number_range, item_with_range):
    assign_number(order.positions.first())  # → 100

    order2 = make_order(event, item_with_range, "TEST2")
    assign_number(order2.positions.first())  # → 101

    order3 = make_order(event, item_with_range, "TEST3")
    bn = assign_number(order3.positions.first())
    assert bn.number == 102


@pytest.mark.django_db
def test_assign_number_kreis_voll(event, number_range, item_with_range):
    number_range.end = 100
    number_range.save()

    order1 = make_order(event, item_with_range, "T1")
    assign_number(order1.positions.first())  # → 100, OK

    order2 = make_order(event, item_with_range, "T2")
    with pytest.raises(ValidationError):
        assign_number(order2.positions.first())


@pytest.mark.django_db
def test_assign_number_noop_wenn_schon_vergeben(order):
    pos = order.positions.first()
    bn1 = assign_number(pos)
    bn2 = assign_number(pos)
    assert bn1.number == bn2.number
    assert BagNumber.objects.filter(position=pos).count() == 1


@pytest.mark.django_db
def test_assign_number_noop_ohne_kreis(event):
    from pretix.base.models import Item, Order, OrderPosition
    item_ohne = Item.objects.create(event=event, name="Ohne", default_price=0)
    sc = event.organizer.sales_channels.first()
    o = Order.objects.create(
        event=event, code="TX", status="n",
        datetime="2026-07-01T12:00:00Z", expires="2026-08-01T12:00:00Z",
        total=0, email="x@x.de", sales_channel=sc,
    )
    pos = OrderPosition.objects.create(order=o, item=item_ohne, price=0)
    assert assign_number(pos) is None
    assert not BagNumber.objects.filter(position=pos).exists()


@pytest.mark.django_db
def test_release_number(order):
    pos = order.positions.first()
    assign_number(pos)
    assert BagNumber.objects.filter(position=pos).exists()
    release_number(pos)
    assert not BagNumber.objects.filter(position=pos).exists()


@pytest.mark.django_db
def test_release_number_noop_ohne_nummer(order):
    release_number(order.positions.first())
