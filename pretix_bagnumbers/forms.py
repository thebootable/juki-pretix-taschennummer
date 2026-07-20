from django import forms
from django.utils.translation import gettext_lazy as _

from .models import ItemNumberConfig, NumberRange, BagNumber


class ItemNumberConfigForm(forms.ModelForm):
    title = _("Bag Number")

    class Meta:
        model = ItemNumberConfig
        fields = ["number_range"]

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["number_range"].queryset = event.bagnumber_ranges.all()
        self.fields["number_range"].required = False
        self.fields["number_range"].label = _("Number range")
        self.fields["number_range"].help_text = _(
            "Leave empty if this product should not receive a bag number. "
            "Manage number ranges under Settings → Bag Numbers."
        )

    def save(self, commit=True):
        if self.cleaned_data.get("number_range") is None:
            if self.instance.pk:
                self.instance.delete()
            return None
        return super().save(commit=commit)


class NumberRangeForm(forms.ModelForm):
    class Meta:
        model = NumberRange
        fields = ["name", "start", "end"]

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._event = event

    def clean(self):
        data = super().clean()
        start = data.get("start")
        end = data.get("end")

        if end is not None and start is not None and end < start:
            raise forms.ValidationError(
                _("End must not be less than start.")
            )

        if start is not None and self._event is not None:
            existing = NumberRange.objects.filter(event=self._event)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            for rng in existing:
                overlaps = (rng.end is None or start <= rng.end) and \
                           (end is None or rng.start <= end)
                if overlaps:
                    raise forms.ValidationError(
                        _("This number range overlaps with '%(name)s' (%(start)s–%(end)s).")
                        % {
                            "name": rng.name,
                            "start": rng.start,
                            "end": rng.end if rng.end is not None else "∞",
                        }
                    )
        return data


class BagNumberChangeForm(forms.ModelForm):
    class Meta:
        model = BagNumber
        fields = ["number"]

    def clean_number(self):
        n = self.cleaned_data["number"]
        clash = BagNumber.objects.filter(
            event=self.instance.event, number=n,
        ).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(
                _("Number %(n)s is already assigned (order %(o)s).")
                % {"n": n, "o": clash.first().position.order.code}
            )
        return n
