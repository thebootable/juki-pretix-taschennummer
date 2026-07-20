import os
import tempfile
from collections import OrderedDict

from django import forms
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from pretix.base.exporter import BaseExporter, ListExporter
from pretix.base.models import Order, OrderPosition, Question
from pretix.helpers.safe_openpyxl import SafeWorkbook

from .models import BagNumber, NumberRange


class BagNumberExporter(ListExporter):
    identifier = "bagnumbers"
    verbose_name = _("Bag Numbers")

    def get_filename(self):
        return "bagnumbers"

    def iterate_list(self, form_data):
        yield [
            str(_("Bag Number")), str(_("Number Range")), str(_("Order Code")),
            str(_("Product")), str(_("Name")), str(_("Status")),
        ]
        qs = BagNumber.objects.filter(
            event=self.event
        ).select_related(
            "position__order", "position__item", "number_range"
        ).order_by("number")
        for tn in qs:
            pos = tn.position
            yield [
                tn.number,
                tn.number_range.name,
                pos.order.code,
                str(pos.item),
                pos.attendee_name or "",
                pos.order.get_status_display(),
            ]


class TeilnehmerdatenExporter(BaseExporter):
    identifier = "teilnehmerdaten"
    verbose_name = _("Participant Data")
    category = pgettext_lazy('export_category', '1 Juki')
    featured = True
    description = _(
        "Excel export with one row per participant (order position with bag number). "
        "Contains order code, bag number, first and last name, all event questions, "
        "invoice address, e-mail, and phone number. "
        "Only paid and pending orders; sorted by bag number ascending. "
        "Choose between all number ranges on one sheet or one sheet per number range."
    )

    def get_filename(self):
        return "teilnehmerdaten"

    @property
    def export_form_fields(self):
        f = OrderedDict([
            ('_format', forms.ChoiceField(
                label=_("Format"),
                choices=[
                    ('all', _("Excel – All number ranges on one sheet")),
                    ('split', _("Excel – One sheet per number range")),
                ],
            )),
            ('items', forms.ModelMultipleChoiceField(
                label=_("Products"),
                queryset=self.event.items.all(),
                widget=forms.CheckboxSelectMultiple(
                    attrs={"class": "scrolling-multiple-choice"}
                ),
                required=False,
                help_text=_("If nothing is selected, all products are included."),
            )),
        ])
        return f

    def _get_questions(self):
        return list(Question.objects.filter(event=self.event).order_by('position', 'pk'))

    def _build_headers(self, questions):
        headers = [
            str(_("Order Code")),
            str(_("Bag Number")),
            str(_("First Name")),
            str(_("Last Name")),
        ]
        for q in questions:
            headers.append(str(q.question))
        headers += [
            str(_("Invoice Address Name")),
            str(_("E-Mail")),
            str(_("Phone Number")),
        ]
        return headers

    def _get_positions_qs(self, form_data):
        qs = OrderPosition.objects.filter(
            order__event=self.event,
            order__status__in=[Order.STATUS_PAID, Order.STATUS_PENDING],
            canceled=False,
            bagnumber__isnull=False,
        )
        if form_data.get('items'):
            qs = qs.filter(item__in=form_data['items'])
        return qs.select_related(
            'order', 'item', 'bagnumber', 'bagnumber__number_range',
        ).prefetch_related(
            'answers', 'answers__question', 'answers__options',
        ).order_by('bagnumber__number')

    def _build_row(self, pos, questions):
        order = pos.order
        bn = pos.bagnumber

        name_parts = pos.attendee_name_parts or {}
        given_name = name_parts.get('given_name', '')
        family_name = name_parts.get('family_name', '')
        if not given_name and not family_name:
            full = pos.attendee_name or ''
            parts = full.split(' ', 1)
            given_name = parts[0] if parts else ''
            family_name = parts[1] if len(parts) > 1 else ''

        row = [
            order.code,
            bn.number,
            given_name,
            family_name,
        ]

        acache = {}
        for a in pos.answers.all():
            if a.question.type in Question.UNLOCALIZED_TYPES:
                acache[a.question_id] = a.answer
            else:
                acache[a.question_id] = str(a)
        for q in questions:
            row.append(acache.get(q.pk, ''))

        try:
            ia_name = order.invoice_address.name or ''
        except Exception:
            ia_name = ''

        row += [
            ia_name,
            order.email or '',
            str(order.phone) if order.phone else '',
        ]
        return row

    def _fill_sheet(self, ws, qs, questions):
        ws.append(self._build_headers(questions))
        for pos in qs:
            ws.append(self._build_row(pos, questions))

    def render(self, form_data, output_file=None):
        questions = self._get_questions()
        variant = form_data.get('_format', 'all')

        wb = SafeWorkbook(write_only=True)

        if variant == 'split':
            ranges = NumberRange.objects.filter(event=self.event).order_by('start')
            for rng in ranges:
                ws = wb.create_sheet(str(rng.name)[:30])
                qs = self._get_positions_qs(form_data).filter(bagnumber__number_range=rng)
                self._fill_sheet(ws, qs, questions)
        else:
            ws = wb.create_sheet(str(_("Participant Data"))[:30])
            self._fill_sheet(ws, self._get_positions_qs(form_data), questions)

        # Windows-compatible: close the NamedTemporaryFile before openpyxl writes to it
        tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        tmp_name = tmp.name
        tmp.close()
        try:
            wb.save(tmp_name)
            if output_file:
                with open(tmp_name, 'rb') as src:
                    output_file.write(src.read())
                return (
                    'teilnehmerdaten.xlsx',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    None,
                )
            else:
                with open(tmp_name, 'rb') as src:
                    data = src.read()
                return (
                    'teilnehmerdaten.xlsx',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    data,
                )
        finally:
            os.unlink(tmp_name)
