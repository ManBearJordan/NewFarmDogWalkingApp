from django import forms
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .models import Pet, Client, Tag, Service
from .models_service_windows import ServiceWindow
from .utils_conflicts import has_conflict

BRISBANE = ZoneInfo("Australia/Brisbane")


class PetForm(forms.ModelForm):
    class Meta:
        model = Pet
        fields = [
            "client",
            "name",
            "species",
            "breed",
            "medications",
            "behaviour",
            "notes",
        ]
        widgets = {
            "medications": forms.Textarea(attrs={"rows": 2}),
            "behaviour": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class ClientForm(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(
        label="Tags",
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Client
        fields = ["name", "email", "phone", "address", "notes", "tags"]

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.status:  # Set default status if not already set
            instance.status = 'active'
        if commit:
            instance.save()
            self.save_m2m()  # Save the many-to-many relationship for tags
        return instance


class ServiceDurationForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ("code", "name", "duration_minutes", "is_active")
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control", "placeholder": "walk30"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Standard Walk (30m)"}),
            "duration_minutes": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class PortalBookingForm(forms.Form):
    service = forms.ModelChoiceField(
        queryset=Service.objects.filter(is_active=True).order_by("name"),
        required=True,
        label="Service",
    )
    date = forms.DateField(required=True, label="Date", widget=forms.DateInput(attrs={"type": "date"}))
    time = forms.TimeField(required=True, label="Start time", widget=forms.TimeInput(attrs={"type": "time"}))
    location = forms.CharField(required=False, max_length=128, initial="Home", label="Location")

    def __init__(self, *args, **kwargs):
        self.client = kwargs.pop("client", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        svc = cleaned.get("service")
        d = cleaned.get("date")
        t = cleaned.get("time")
        if not (svc and d and t):
            return cleaned
        if not svc.duration_minutes:
            self.add_error("service", "This service has no duration set; contact support.")
            return cleaned
        # Compute naive local datetimes (app expects naive local)
        start_dt = datetime(d.year, d.month, d.day, t.hour, t.minute)
        end_dt = start_dt + timedelta(minutes=svc.duration_minutes)
        cleaned["start_dt"] = start_dt
        cleaned["end_dt"] = end_dt
        if self.client is None:
            return cleaned
        if has_conflict(self.client, start_dt, end_dt):
            self.add_error(None, "That time conflicts with an existing booking.")
            return cleaned
        
        # Enforce ServiceWindow constraints for client portal
        # Convert naive local datetime to aware for timezone comparisons
        aware_start = start_dt.replace(tzinfo=BRISBANE)
        aware_end = end_dt.replace(tzinfo=BRISBANE)
        win_qs = ServiceWindow.objects.filter(active=True, block_in_portal=True)
        for w in win_qs:
            if w.applies_on(aware_start) and w.overlaps(aware_start, aware_end) and w.blocks_service_in_portal(svc):
                self.add_error(None, 
                    f'"{svc.name}" is not bookable during {w.title} ({w.start_time}–{w.end_time}). '
                    "Please choose another time."
                )
                break
        return cleaned