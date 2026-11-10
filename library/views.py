from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BookForm
from .models import Book, BookRequest

ACTIVE_STATUSES = [
    BookRequest.Status.PENDING,
    BookRequest.Status.APPROVED,
    BookRequest.Status.RECEIVED,
]


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
def book_request(request, pk):
    if request.method != "POST":
        return redirect("home")
    book = get_object_or_404(Book, pk=pk, in_pool=True)
    if book.owner == request.user:
        messages.error(request, "Bu kitap zaten senin.")
    elif book.holder:
        messages.error(request, "Bu kitap şu an başkasında.")
    elif BookRequest.objects.filter(
        book=book, requester=request.user, status__in=ACTIVE_STATUSES
    ).exists():
        messages.info(request, "Bu kitap için zaten bir talebin var.")
    else:
        BookRequest.objects.create(book=book, requester=request.user, owner=book.owner)
        messages.success(request, "Talebin sahibine iletildi.")
    return redirect("home")


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
def book_toggle_pool(request, pk):
    if request.method == "POST":
        book = get_object_or_404(Book, pk=pk, owner=request.user)
        book.in_pool = not book.in_pool
        book.save(update_fields=["in_pool"])
    return redirect("my_books")