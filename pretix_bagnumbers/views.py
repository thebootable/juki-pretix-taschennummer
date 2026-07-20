from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.views import View
from django.views.generic import FormView, TemplateView

from pretix.control.permissions import EventPermissionRequiredMixin
from pretix.control.views.event import EventSettingsViewMixin

from .forms import NumberRangeForm, BagNumberChangeForm
from .models import ItemNumberConfig, NumberRange, BagNumber


class OverviewView(EventSettingsViewMixin, EventPermissionRequiredMixin, TemplateView):
    """
    Zentrale Seite unter Einstellungen → Taschennummern:
    - alle Nummernkreise (anlegen/bearbeiten/löschen)
    - alle konfigurierten Produkte mit Sprunglink zur Produktseite
    - Liste der vergebenen Nummern mit Änderungsmöglichkeit
    """
    template_name = "pretix_bagnumbers/overview.html"
    permission = "can_change_event_settings"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = self.request.event
        ctx["ranges"] = event.bagnumber_ranges.annotate(
            numbers_count=Count("numbers")
        ).prefetch_related("items__item")
        ctx["configs"] = ItemNumberConfig.objects.filter(
            item__event=event
        ).select_related("item", "number_range")
        ctx["numbers"] = BagNumber.objects.filter(
            event=event
        ).select_related(
            "position__order", "position__item", "number_range"
        )
        # Sprunglink zurück zum Produkt:
        # reverse("control:event.item", kwargs={organizer, event, item=pk})
        # -> im Template verwendet
        return ctx


class RangeCreateUpdateView(EventSettingsViewMixin, EventPermissionRequiredMixin, FormView):
    template_name = "pretix_bagnumbers/range_form.html"
    permission = "can_change_event_settings"
    form_class = NumberRangeForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        pk = self.kwargs.get("pk")
        if pk:
            kwargs["instance"] = get_object_or_404(
                NumberRange, pk=pk, event=self.request.event
            )
        return kwargs

    def form_valid(self, form):
        form.instance.event = self.request.event
        form.save()
        messages.success(self.request, _("Nummernkreis gespeichert."))
        return redirect(self._overview_url())

    def _overview_url(self):
        return reverse(
            "plugins:pretix_bagnumbers:overview",
            kwargs={
                "organizer": self.request.organizer.slug,
                "event": self.request.event.slug,
            },
        )


class RangeDeleteView(EventPermissionRequiredMixin, View):
    """
    Löscht einen Nummernkreis -- nur wenn keine Nummern vergeben sind.
    Der Button wird im Template nur bei leeren Kreisen angezeigt;
    diese View ist das serverseitige Sicherheitsnetz dazu.
    """
    permission = "can_change_event_settings"

    def post(self, request, *args, **kwargs):
        rng = get_object_or_404(
            NumberRange, pk=kwargs["pk"], event=request.event
        )
        if rng.numbers.exists():
            messages.error(request, _(
                "Der Nummernkreis '%(name)s' kann nicht gelöscht werden, "
                "solange Nummern daraus vergeben sind."
            ) % {"name": rng.name})
        else:
            try:
                rng.delete()
                messages.success(request, _("Nummernkreis gelöscht."))
            except ProtectedError:
                # Race: zwischen Prüfung und Löschen wurde eine Nummer
                # vergeben. PROTECT im Model fängt das hart ab.
                messages.error(request, _(
                    "Der Nummernkreis konnte nicht gelöscht werden, da "
                    "inzwischen Nummern daraus vergeben wurden."
                ))
        return redirect(reverse(
            "plugins:pretix_bagnumbers:overview",
            kwargs={
                "organizer": request.organizer.slug,
                "event": request.event.slug,
            },
        ))


class NumberChangeView(EventSettingsViewMixin, EventPermissionRequiredMixin, FormView):
    """Manuelle Änderung einer einzelnen Nummer."""
    template_name = "pretix_bagnumbers/number_form.html"
    permission = "can_change_orders"
    form_class = BagNumberChangeForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = get_object_or_404(
            BagNumber, pk=self.kwargs["pk"], event=self.request.event
        )
        return kwargs

    def form_valid(self, form):
        old_number = BagNumber.objects.get(pk=form.instance.pk).number
        form.save()
        form.instance.position.order.log_action(
            "pretix_bagnumbers.number.changed",
            user=self.request.user,
            data={
                "old_number": old_number,
                "number": form.instance.number,
                "positionid": form.instance.position.positionid,
            },
        )
        messages.success(self.request, _("Nummer geändert."))
        return redirect(reverse(
            "plugins:pretix_bagnumbers:overview",
            kwargs={
                "organizer": self.request.organizer.slug,
                "event": self.request.event.slug,
            },
        ))
