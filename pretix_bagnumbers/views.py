from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.db.models import Count
from django.views import View
from django.views.generic import FormView, TemplateView

from pretix.base.models import Item, Order, OrderPosition
from pretix.control.permissions import EventPermissionRequiredMixin

from .forms import NumberRangeForm, BagNumberChangeForm
from .models import ItemNumberConfig, NumberRange, BagNumber
from .services import assign_number, release_number


class OverviewView(EventPermissionRequiredMixin, TemplateView):
    template_name = "pretix_bagnumbers/overview.html"
    permission = "can_change_event_settings"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = self.request.event

        # Fetch all assigned numbers in one query, grouped by range
        numbers_by_range = {}
        for row in BagNumber.objects.filter(event=event).values("number_range_id", "number"):
            numbers_by_range.setdefault(row["number_range_id"], []).append(row["number"])

        ranges = list(
            event.bagnumber_ranges.annotate(numbers_count=Count("numbers"))
        )
        for rng in ranges:
            assigned = sorted(numbers_by_range.get(rng.pk, []))
            if assigned:
                max_n = assigned[-1]
                assigned_set = set(assigned)
                rng.gaps = [n for n in range(rng.start, max_n) if n not in assigned_set]
            else:
                rng.gaps = []
        ctx["ranges"] = ranges

        ctx["configs"] = ItemNumberConfig.objects.filter(
            item__event=event
        ).select_related("item", "number_range")

        ctx["numbers"] = BagNumber.objects.filter(
            event=event
        ).select_related(
            "position__order", "position__item", "number_range"
        )

        ctx["unassigned_count"] = OrderPosition.objects.filter(
            order__event=event,
            order__status__in=[Order.STATUS_PAID, Order.STATUS_PENDING],
            canceled=False,
            item__bagnumber_config__isnull=False,
            bagnumber__isnull=True,
        ).count()

        return ctx


class RangeCreateUpdateView(EventPermissionRequiredMixin, FormView):
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
        kwargs["event"] = self.request.event
        return kwargs

    def form_valid(self, form):
        form.instance.event = self.request.event
        form.save()
        messages.success(self.request, _("Number range saved."))
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
    permission = "can_change_event_settings"

    def post(self, request, *args, **kwargs):
        rng = get_object_or_404(NumberRange, pk=kwargs["pk"], event=request.event)
        overview_url = reverse(
            "plugins:pretix_bagnumbers:overview",
            kwargs={"organizer": request.organizer.slug, "event": request.event.slug},
        )

        if rng.numbers.exists() and request.POST.get("force") != "1":
            return redirect(reverse(
                "plugins:pretix_bagnumbers:range.delete.confirm",
                kwargs={"organizer": request.organizer.slug, "event": request.event.slug, "pk": rng.pk},
            ))

        # Release all bag numbers with proper logging before deleting the range
        for bn in BagNumber.objects.filter(number_range=rng).select_related("position"):
            release_number(bn.position)

        rng.delete()  # cascades to ItemNumberConfig
        messages.success(request, _("Number range deleted."))
        return redirect(overview_url)


class RangeDeleteConfirmView(EventPermissionRequiredMixin, TemplateView):
    template_name = "pretix_bagnumbers/range_delete_confirm.html"
    permission = "can_change_event_settings"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rng = get_object_or_404(NumberRange, pk=self.kwargs["pk"], event=self.request.event)
        ctx["range"] = rng
        ctx["number_count"] = rng.numbers.count()
        ctx["affected_configs"] = ItemNumberConfig.objects.filter(
            number_range=rng
        ).select_related("item")
        return ctx


class BulkAssignView(EventPermissionRequiredMixin, View):
    permission = "can_change_orders"

    def post(self, request, *args, **kwargs):
        item = get_object_or_404(Item, pk=kwargs["item_pk"], event=request.event)
        overview_url = reverse(
            "plugins:pretix_bagnumbers:overview",
            kwargs={"organizer": request.organizer.slug, "event": request.event.slug},
        )

        try:
            item.bagnumber_config
        except ItemNumberConfig.DoesNotExist:
            messages.error(request, _("No number range configured for this product."))
            return redirect(overview_url)

        positions = OrderPosition.objects.filter(
            order__event=request.event,
            order__status__in=[Order.STATUS_PAID, Order.STATUS_PENDING],
            item=item,
            canceled=False,
            bagnumber__isnull=True,
        )

        assigned = 0
        range_full = False
        for pos in positions:
            try:
                if assign_number(pos):
                    assigned += 1
            except ValidationError:
                range_full = True
                break

        if assigned:
            messages.success(request, _("%(count)s numbers assigned.") % {"count": assigned})
        if range_full:
            messages.warning(request, _(
                "The number range is full. Not all positions could be assigned a number."
            ))
        if not assigned and not range_full:
            messages.info(request, _("No orders found that still need a number."))

        return redirect(overview_url)


class NumberChangeView(EventPermissionRequiredMixin, FormView):
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
        old_number = form.initial["number"]
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
        messages.success(self.request, _("Number changed."))
        return redirect(reverse(
            "plugins:pretix_bagnumbers:overview",
            kwargs={
                "organizer": self.request.organizer.slug,
                "event": self.request.event.slug,
            },
        ))
