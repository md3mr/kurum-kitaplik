import json
from unittest.mock import patch

from django.test import SimpleTestCase

from .services import (
    InvalidISBN,
    _to10,
    _to13,
    _valid10,
    _valid13,
    candidates,
    clean_isbn,
    lookup_isbn,
)


class CleanISBNTests(SimpleTestCase):
    def test_tire_ve_bosluk_temizlenir(self):
        self.assertEqual(clean_isbn("978-975-08-4598-7"), "9789750845987")
        self.assertEqual(clean_isbn(" 0 306 40615 2 "), "0306406152")

    def test_x_buyuk_harfe_cevrilir(self):
        self.assertEqual(clean_isbn("080442957x"), "080442957X")

    def test_bos_girdi(self):
        self.assertEqual(clean_isbn(""), "")
        self.assertEqual(clean_isbn(None), "")


class ValidationTests(SimpleTestCase):
    def test_gecerli_13(self):
        self.assertTrue(_valid13("9780306406157"))
        self.assertTrue(_valid13("9789750845987"))

    def test_gecersiz_13(self):
        self.assertFalse(_valid13("9780306406158"))
        self.assertFalse(_valid13("1234567890123"))

    def test_gecerli_10(self):
        self.assertTrue(_valid10("0306406152"))
        self.assertTrue(_valid10("080442957X"))

    def test_gecersiz_10(self):
        self.assertFalse(_valid10("0306406153"))
        self.assertFalse(_valid10("1234567890"))


class ConversionTests(SimpleTestCase):
    def test_10_dan_13_e(self):
        self.assertEqual(_to13("0306406152"), "9780306406157")

    def test_13_den_10_a(self):
        self.assertEqual(_to10("9780306406157"), "0306406152")

    def test_x_ile_10_dan_13_e(self):
        # 080442957X → 9780804429573
        self.assertEqual(_to13("080442957X"), "9780804429573")


class CandidatesTests(SimpleTestCase):
    def test_gecerli_13_once_doner(self):
        result = candidates("978-0-306-40615-7")
        self.assertEqual(result[0], "9780306406157")
        self.assertIn("0306406152", result)

    def test_gecerli_10_once_13_doner(self):
        result = candidates("0-306-40615-2")
        self.assertEqual(result[0], "9780306406157")

    def test_gecersiz_isbn_hata_atar(self):
        with self.assertRaises(InvalidISBN):
            candidates("123")
        with self.assertRaises(InvalidISBN):
            candidates("1234567890123")  # Check digit yanlış
        with self.assertRaises(InvalidISBN):
            candidates("")


class LookupISBNTests(SimpleTestCase):
    """Ağ çağrılarını mock'layarak test."""

    @patch("library.services._open_library")
    def test_open_library_basariliysa_sonuc_doner(self, mock_openlib):
        mock_openlib.return_value = {
            "title": "Suç ve Ceza",
            "author": "Dostoyevski",
            "publisher": "İş Bankası",
            "cover_url": "https://example.com/cover.jpg",
        }
        result = lookup_isbn("9780306406157")
        self.assertEqual(result["title"], "Suç ve Ceza")
        self.assertEqual(result["isbn"], "9780306406157")

    @patch("library.services._google_books")
    @patch("library.services._open_library")
    def test_open_library_bulunamazsa_google_denenir(self, mock_openlib, mock_google):
        mock_openlib.return_value = None
        mock_google.return_value = {
            "title": "Google'dan",
            "author": "Yazar",
            "publisher": "",
            "cover_url": "",
        }
        result = lookup_isbn("9780306406157")
        self.assertEqual(result["title"], "Google'dan")

    @patch("library.services._google_books")
    @patch("library.services._open_library")
    def test_ikisi_de_bulamazsa_none_doner(self, mock_openlib, mock_google):
        mock_openlib.return_value = None
        mock_google.return_value = None
        result = lookup_isbn("9780306406157")
        self.assertIsNone(result)

    def test_gecersiz_isbn_hatasi(self):
        with self.assertRaises(InvalidISBN):
            lookup_isbn("123")