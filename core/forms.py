from django import forms
from .models import Pet, Client, Tag, Service


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