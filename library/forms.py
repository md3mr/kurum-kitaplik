from django import forms

from .models import Book


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ["title", "author", "publisher", "isbn", "in_pool"]
        labels = {
            "title": "Kitap adı",
            "author": "Yazar",
            "publisher": "Yayıncı",
            "isbn": "ISBN",
            "in_pool": "Ortak havuzda görünsün (başkaları talep edebilsin)",
        }