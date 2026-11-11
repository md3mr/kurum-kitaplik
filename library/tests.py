from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Book, BookRequest, Notification

User = get_user_model()


class BaseTestCase(TestCase):
    """Tüm testler için ortak kurulum."""

    def setUp(self):
        self.ali = User.objects.create_user(username="ali", password="test123")
        self.veli = User.objects.create_user(username="veli", password="test123")
        self.ayse = User.objects.create_user(username="ayse", password="test123")

        self.book = Book.objects.create(
            owner=self.ali,
            title="Suç ve Ceza",
            author="Dostoyevski",
            in_pool=True,
        )


class BookRequestPermissionTests(BaseTestCase):
    """Talep gönderme yetkileri."""

    def test_kullanici_kendi_kitabini_talep_edemez(self):
        self.client.login(username="ali", password="test123")
        self.client.post(reverse("book_request", args=[self.book.pk]))
        self.assertEqual(BookRequest.objects.count(), 0)

    def test_baskasinin_kitabini_talep_edebilir(self):
        self.client.login(username="veli", password="test123")
        self.client.post(reverse("book_request", args=[self.book.pk]))
        self.assertEqual(BookRequest.objects.count(), 1)
        req = BookRequest.objects.first()
        self.assertEqual(req.requester, self.veli)
        self.assertEqual(req.owner, self.ali)
        self.assertEqual(req.status, BookRequest.Status.PENDING)

    def test_ayni_kitaba_ikinci_talep_engellenir(self):
        self.client.login(username="veli", password="test123")
        self.client.post(reverse("book_request", args=[self.book.pk]))
        self.client.post(reverse("book_request", args=[self.book.pk]))
        # Sadece 1 tane olmalı
        self.assertEqual(BookRequest.objects.filter(book=self.book).count(), 1)

    def test_oduncteki_kitap_talep_edilemez(self):
        self.book.holder = self.ayse
        self.book.save()
        self.client.login(username="veli", password="test123")
        self.client.post(reverse("book_request", args=[self.book.pk]))
        self.assertEqual(BookRequest.objects.count(), 0)

    def test_havuzda_olmayan_kitap_talep_edilemez(self):
        self.book.in_pool = False
        self.book.save()
        self.client.login(username="veli", password="test123")
        response = self.client.post(reverse("book_request", args=[self.book.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(BookRequest.objects.count(), 0)


class BookRequestNotificationTests(BaseTestCase):
    """Bildirim gönderimi."""

    def test_talep_gonderilince_sahibe_bildirim_gider(self):
        self.client.login(username="veli", password="test123")
        self.client.post(reverse("book_request", args=[self.book.pk]))
        notes = Notification.objects.filter(user=self.ali)
        self.assertEqual(notes.count(), 1)
        self.assertIn("Suç ve Ceza", notes.first().message)
        self.assertIn("veli", notes.first().message)
        self.assertFalse(notes.first().is_read)

    def test_onaylaninca_talep_edene_bildirim_gider(self):
        req = BookRequest.objects.create(
            book=self.book, requester=self.veli, owner=self.ali
        )
        self.client.login(username="ali", password="test123")
        self.client.post(reverse("request_action", args=[req.pk, "approve"]))

        req.refresh_from_db()
        self.assertEqual(req.status, BookRequest.Status.APPROVED)

        # Veli'ye bildirim gitti mi?
        notes = Notification.objects.filter(user=self.veli)
        self.assertEqual(notes.count(), 1)
        self.assertIn("onaylandı", notes.first().message)

    def test_reddedilince_talep_edene_bildirim_gider(self):
        req = BookRequest.objects.create(
            book=self.book, requester=self.veli, owner=self.ali
        )
        self.client.login(username="ali", password="test123")
        self.client.post(reverse("request_action", args=[req.pk, "reject"]))

        req.refresh_from_db()
        self.assertEqual(req.status, BookRequest.Status.REJECTED)

        notes = Notification.objects.filter(user=self.veli)
        self.assertEqual(notes.count(), 1)
        self.assertIn("reddedildi", notes.first().message)

    def test_iade_alinca_talep_edene_bildirim_gider(self):
        req = BookRequest.objects.create(
            book=self.book, requester=self.veli, owner=self.ali,
            status=BookRequest.Status.RECEIVED,
        )
        self.book.holder = self.veli
        self.book.save()

        self.client.login(username="ali", password="test123")
        self.client.post(reverse("request_action", args=[req.pk, "returned"]))

        req.refresh_from_db()
        self.assertEqual(req.status, BookRequest.Status.RETURNED)

        notes = Notification.objects.filter(user=self.veli)
        self.assertGreaterEqual(notes.count(), 1)
        self.assertTrue(any("iade" in n.message.lower() for n in notes))


class RequestActionPermissionTests(BaseTestCase):
    """Talep aksiyonlarında yetki kontrolü."""

    def setUp(self):
        super().setUp()
        self.req = BookRequest.objects.create(
            book=self.book, requester=self.veli, owner=self.ali
        )

    def test_yetkisiz_kullanici_onaylayamaz(self):
        # Ayşe ne sahip ne talep eden
        self.client.login(username="ayse", password="test123")
        response = self.client.post(
            reverse("request_action", args=[self.req.pk, "approve"])
        )
        self.assertEqual(response.status_code, 404)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, BookRequest.Status.PENDING)

    def test_talep_eden_kendi_talebini_onaylayamaz(self):
        # Veli talep eden ama onaylayan değil
        self.client.login(username="veli", password="test123")
        self.client.post(reverse("request_action", args=[self.req.pk, "approve"]))
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, BookRequest.Status.PENDING)

    def test_gecersiz_action_404_doner(self):
        self.client.login(username="ali", password="test123")
        response = self.client.post(
            reverse("request_action", args=[self.req.pk, "hackle"])
        )
        self.assertEqual(response.status_code, 404)


class BookHolderFlowTests(BaseTestCase):
    """Kitap ödünç verme/iade alma akışı."""

    def test_onaylaninca_holder_talep_edene_atanir(self):
        req = BookRequest.objects.create(
            book=self.book, requester=self.veli, owner=self.ali
        )
        self.client.login(username="ali", password="test123")
        self.client.post(reverse("request_action", args=[req.pk, "approve"]))

        self.book.refresh_from_db()
        self.assertEqual(self.book.holder, self.veli)

    def test_iade_alinca_holder_temizlenir(self):
        req = BookRequest.objects.create(
            book=self.book, requester=self.veli, owner=self.ali,
            status=BookRequest.Status.RECEIVED,
        )
        self.book.holder = self.veli
        self.book.save()

        self.client.login(username="ali", password="test123")
        self.client.post(reverse("request_action", args=[req.pk, "returned"]))

        self.book.refresh_from_db()
        self.assertIsNone(self.book.holder)

    def test_oduncteki_kitap_havuzdan_cikarilamaz(self):
        self.book.holder = self.veli
        self.book.save()

        self.client.login(username="ali", password="test123")
        self.client.post(reverse("book_toggle_pool", args=[self.book.pk]))

        self.book.refresh_from_db()
        self.assertTrue(self.book.in_pool)  # Değişmemiş olmalı

    def test_musait_kitap_havuzdan_cikarilabilir(self):
        self.client.login(username="ali", password="test123")
        self.client.post(reverse("book_toggle_pool", args=[self.book.pk]))

        self.book.refresh_from_db()
        self.assertFalse(self.book.in_pool)


class NotificationPageTests(BaseTestCase):
    """Bildirimler sayfası."""

    def test_login_olmadan_erisilemez(self):
        response = self.client.get(reverse("notifications"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_bildirimler_sayfasi_okunmamisleri_okur(self):
        Notification.objects.create(
            user=self.ali, message="Test bildirimi", book=self.book
        )
        self.client.login(username="ali", password="test123")
        self.client.get(reverse("notifications"))

        note = Notification.objects.filter(user=self.ali).first()
        self.assertTrue(note.is_read)

    def test_sadece_kendi_bildirimlerini_gorur(self):
        Notification.objects.create(user=self.ali, message="Ali'ye özel mesaj")
        Notification.objects.create(user=self.veli, message="Veli'ye özel mesaj")

        self.client.login(username="ali", password="test123")
        response = self.client.get(reverse("notifications"))

        # Django template'leri tek tırnağı &#x27; olarak escape eder.
        # Bu yüzden ham içerikte kontrol ediyoruz.
        content = response.content.decode("utf-8")
        self.assertIn("Ali", content)
        self.assertNotIn("Veli", content)
        self.assertNotIn("Veli'ye özel mesaj", content)