from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import NewsPost


def news_list(request):
    qs = NewsPost.objects.published().select_related().prefetch_related("images")
    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "news/list.html", {"page": page})


def news_detail(request, slug: str):
    post = get_object_or_404(
        NewsPost.objects.published().prefetch_related("images"),
        slug=slug,
    )
    return render(request, "news/detail.html", {"post": post})
