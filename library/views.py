from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BookForm
from .models import Book, BookRequest, Notification
from .services import InvalidISBN, lookup_isbn

ACTIVE_STATUSES = [
    BookRequest.Status.PENDING,
    BookRequest.Status.APPROVED,
    BookRequest.Status.RECEIVED,
]

VALID_REQUEST_ACTIONS = {"approve", "reject", "cancel", "received", "returned"}


@login_required
def home(request):
    q = request.GET.get("q", "").strip()
    show_all = request.GET.get("show_all") == "1"

    books = Book.objects.filter(in_pool=True).select_related("owner", "holder")
    if q:
        books = books.filter(
            Q(title__icontains=q) | Q(author__icontains=q) | Q(isbn__icontains=q)
        )
    if not show_all:
        books = books.filter(holder__isnull=True)
    books = books.order_by("holder", "-created_at")

    my_requested = set(
        BookRequest.objects.filter(
            requester=request.user, status__in=ACTIVE_STATUSES
        ).values_list("book_id", flat=True)
    )
    return render(request, "library/home.html", {
        "books": books,
        "q": q,
        "show_all": show_all,
        "my_requested": my_requested,
    })


@login_required
@transaction.atomic
def book_request(request, pk):
    book = get_object_or_404(
        Book.objects.select_for_update().filter(pk=pk, in_pool=True)
    )

    if book.owner == request.user:
        messages.error(request, "Bu kitap zaten senin.")
        return redirect("home")
    if book.holder:
        messages.error(request, "Bu kitap şu an başkasında.")
        return redirect("home")
    if BookRequest.objects.filter(
        book=book, requester=request.user, status__in=ACTIVE_STATUSES
    ).exists():
        messages.info(request, "Bu kitap için zaten bir talebin var.")
        return redirect("home")

    if request.method == "POST":
        BookRequest.objects.create(book=book, requester=request.user, owner=book.owner)

        # Kitap sahibine: kim, hangi kitabı istedi
        Notification.objects.create(
            user=book.owner,
            book=book,
            message=(
                f"{request.user.username}, '{book.title}' kitabını talep etti. "
                f"Onaylamak ya da reddetmek için Taleplerim → Gelen sekmesine bakabilirsin."
            ),
            link="/requests/?tab=in",
        )

        messages.success(request, f"Talebin {book.owner.username} adlı kişiye iletildi.")
        return redirect("home")

    return render(request, "library/request_confirm.html", {"book": book})


@login_required
def my_books(request):
    books = Book.objects.filter(owner=request.user).order_by("-created_at")
    return render(request, "library/my_books.html", {"books": books})


@login_required
def book_add(request):
    if request.method == "POST":
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save(commit=False)
            book.owner = request.user
            book.save()
            messages.success(request, "Kitap eklendi.")
            return redirect("my_books")
    else:
        form = BookForm()
    return render(request, "library/book_form.html", {"form": form})


@login_required
def isbn_lookup(request):
    try:
        result = lookup_isbn(request.GET.get("isbn", ""))
    except InvalidISBN:
        return JsonResponse(
            {"error": "ISBN numarası geçersiz görünüyor. Numarayı kontrol edin."},
            status=400,
        )
    except (OSError, ValueError):
        return JsonResponse(
            {"error": "Kitap servislerine ulaşılamadı. Bilgileri elle girebilirsiniz."},
            status=502,
        )
    if result is None:
        return JsonResponse(
            {"error": "Bu ISBN hiçbir kaynakta bulunamadı. Bilgileri elle girebilirsiniz."},
            status=404,
        )
    return JsonResponse(result)


@login_required
def book_toggle_pool(request, pk):
    if request.method == "POST":
        book = get_object_or_404(Book, pk=pk, owner=request.user)
        if book.holder and book.in_pool:
            messages.error(
                request,
                "Kitap şu an birinde ödünçte. İade alındıktan sonra havuzdan çıkarabilirsin.",
            )
            return redirect("my_books")
        book.in_pool = not book.in_pool
        book.save(update_fields=["in_pool"])
    return redirect("my_books")


@login_required
def requests_list(request):
    tab = request.GET.get("tab", "in")
    base = BookRequest.objects.select_related("book", "requester", "owner")

    if tab == "out":
        items = base.filter(requester=request.user).order_by("-created_at")
    else:
        tab = "in"
        items = base.filter(owner=request.user).order_by("-created_at")

    incoming_open = BookRequest.objects.filter(
        owner=request.user,
        status__in=[BookRequest.Status.PENDING, BookRequest.Status.RECEIVED],
    ).count()
    return render(request, "library/requests.html", {
        "items": items,
        "tab": tab,
        "incoming_open": incoming_open,
    })


@login_required
def notifications_list(request):
    notes = (
        request.user.notifications
        .select_related("book")
        .order_by("-created_at")
    )
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, "library/notifications.html", {"notifications": notes})


@login_required
@transaction.atomic
def request_action(request, pk, action):
    if action not in VALID_REQUEST_ACTIONS:
        raise Http404("Geçersiz işlem.")
    if request.method != "POST":
        return redirect("requests")

    req = get_object_or_404(
        BookRequest.objects.select_for_update(of=("self", "book"))
        .select_related("book", "requester", "owner")
        .filter(Q(owner=request.user) | Q(requester=request.user)),
        pk=pk,
    )

    book = req.book
    me = request.user
    S = BookRequest.Status
    is_owner = req.owner_id == me.id
    is_requester = req.requester_id == me.id
    tab = "in" if is_owner else "out"

    # Bildirim mesajlarında kullanılacak kısa değişkenler
    kitap = book.title
    isteyen = req.requester.username
    sahip = req.owner.username

    if action == "approve" and is_owner and req.status == S.PENDING:
        if book.holder_id:
            messages.error(request, "Bu kitap şu an başkasında.")
        else:
            req.status = S.APPROVED
            req.save()
            book.holder = req.requester
            book.save(update_fields=["holder"])
            Notification.objects.create(
                user=req.requester,
                book=book,
                message=(
                    f"'{kitap}' için {sahip} tarafından gönderilen talebin onaylandı. "
                    f"Kitabı teslim alabilirsin."
                ),
                link="/requests/?tab=out",
            )
            messages.success(request, "Talep onaylandı.")

    elif action == "reject" and is_owner and req.status == S.PENDING:
        req.status = S.REJECTED
        req.save()
        Notification.objects.create(
            user=req.requester,
            book=book,
            message=(
                f"'{kitap}' için {sahip} tarafından gönderilen talebin reddedildi."
            ),
            link="/requests/?tab=out",
        )
        messages.info(request, "Talep reddedildi.")

    elif action == "cancel" and is_requester and req.status in (S.PENDING, S.APPROVED):
        if req.status == S.APPROVED and book.holder_id == me.id:
            book.holder = None
            book.save(update_fields=["holder"])
        req.status = S.CANCELLED
        req.save()
        Notification.objects.create(
            user=req.owner,
            book=book,
            message=(
                f"{isteyen}, '{kitap}' için {sahip}'a gönderdiği talebinden vazgeçti."
            ),
            link="/requests/?tab=in",
        )
        messages.info(request, "Talepten vazgeçildi.")

    elif action == "received" and is_requester and req.status == S.APPROVED:
        req.status = S.RECEIVED
        req.save()
        Notification.objects.create(
            user=req.owner,
            book=book,
            message=(
                f"{isteyen}, '{kitap}' için {sahip}'tan aldığı kitabı teslim aldı."
            ),
            link="/requests/?tab=in",
        )
        messages.success(request, "Teslim alındı olarak işaretlendi.")

    elif action == "returned" and is_owner and req.status in (S.APPROVED, S.RECEIVED):
        req.status = S.RETURNED
        req.save()
        book.holder = None
        book.save(update_fields=["holder"])
        Notification.objects.create(
            user=req.requester,
            book=book,
            message=(
                f"'{kitap}' için {sahip}'a verdiğin kitap iade alındı. Teşekkürler!"
            ),
            link="/requests/?tab=out",
        )
        messages.success(request, "Kitap iade alındı, tekrar havuzda müsait.")

    else:
        messages.error(request, "Bu işlem şu an yapılamaz.")

    return redirect(f"/requests/?tab={tab}")