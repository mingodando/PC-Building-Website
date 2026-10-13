from django import forms

from .models import Order


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = (
            'full_name', 'email', 'phone', 'address', 'city', 'postal_code',
            'delivery_method', 'payment_method', 'notes',
        )
        widgets = {
            'delivery_method': forms.RadioSelect,
            'payment_method': forms.RadioSelect,
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Anything we should know? (optional)'}),
            'address': forms.TextInput(attrs={'placeholder': 'House number, street, sub-district'}),
            'phone': forms.TextInput(attrs={'placeholder': '08X XXX XXXX', 'autocomplete': 'tel'}),
            'postal_code': forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'postal-code'}),
        }
        labels = {
            'address': 'Address',
            'city': 'City / Province',
        }

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        digits = ''.join(ch for ch in phone if ch.isdigit())
        if not 9 <= len(digits) <= 15:
            raise forms.ValidationError("Enter a valid phone number.")
        return phone

    def clean_postal_code(self):
        code = self.cleaned_data['postal_code'].strip()
        if not (code.isdigit() and len(code) == 5):
            raise forms.ValidationError("Postal codes are 5 digits.")
        return code
