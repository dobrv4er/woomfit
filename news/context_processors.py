from .models import NewsPost

def top_news(request):
    return {
        "top_news": NewsPost.objects.published().only("id", "title", "slug", "badge", "card_style", "cover", "published_at")[:3]
    }
