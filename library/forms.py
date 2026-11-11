from django import forms

from .models import Book
from .services import InvalidISBN, candidates


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ["title", "author", "publisher", "isbn", "cover_url", "in_pool"]
        labels = {
            "title": "Kitap adı",
            "author": "Yazar",
            "publisher": "Yayıncı",
            "isbn": "ISBN",
            "in_pool": "Ortak havuzda görünsün (başkaları talep edebilsin)",
        }
        widgets = {
            "cover_url": forms.HiddenInput(),
            "isbn": forms.TextInput(attrs={
                "placeholder": "9789750845987 veya 9750845981",
                "inputmode": "numeric",
                "autocomplete": "off",
            }),
        }

    def clean_isbn(self):
        """ISBN girildiyse geçerliliğini kontrol et. Boş bırakılabilir."""
        raw = self.cleaned_data.get("isbn", "").strip()
        if not raw:
            return ""
        try:
            formats = candidates(raw)  # Geçerliyse format listesi döner
        except InvalidISBN:
            raise forms.ValidationError(
                "Geçersiz ISBN. 10 veya 13 haneli, kontrol hanesi doğru bir numara girin."
            )
        # 13 haneli formatı normalize et (10 haneliyse 13'e çevir)
        return formats[0]

    def clean(self):
        cleaned = super().clean()
        in_pool = cleaned.get("in_pool")
        # Yeni kitap eklerken havuzdaysa ISBN zorunlu olmasın, sadece tutarlılık için
        # (istersen buraya ek kural koyabilirsin)
        return cleaned