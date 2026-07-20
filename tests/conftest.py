"""
Gemeinsame Fixtures für alle Tests.
"""
import pytest
from django_scopes import scopes_disabled


@pytest.fixture(autouse=True)
def no_scope(db):
    """Deaktiviert django-scopes für die gesamte Testlaufzeit.

    Pretix scopet nahezu alle Modell-Manager; ohne dieses Fixture schlägt
    jeder ORM-Zugriff mit ScopeError fehl, auch inner halb von Signal-Handlern.
    """
    with scopes_disabled():
        yield


@pytest.fixture
def organizer(db):
    from pretix.base.models import Organizer
    return Organizer.objects.create(name="Test-Org", slug="testorg")


@pytest.fixture
def event(organizer):
    from pretix.base.models import Event
    return Event.objects.create(
        organizer=organizer,
        name="Testveranstaltung",
        slug="testev",
        date_from="2026-08-01",
        plugins="pretix_bagnumbers",
    )


def make_order(event, item, code):
    from pretix.base.models import Order, OrderPosition
    sc = event.organizer.sales_channels.first()
    o = Order.objects.create(
        event=event,
        code=code,
        status=Order.STATUS_PENDING,
        datetime="2026-07-01T12:00:00Z",
        expires="2026-08-01T12:00:00Z",
        total=0,
        email="test@example.com",
        sales_channel=sc,
    )
    OrderPosition.objects.create(order=o, item=item, price=0)
    return o
