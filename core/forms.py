from django import forms
from .models import Pet


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