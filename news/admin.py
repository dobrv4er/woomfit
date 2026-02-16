from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import NewsPost, NewsImage


class NewsPostAdminForm(forms.ModelForm):
    class Meta:
        model = NewsPost
        fields = "__all__"
        widgets = {
            "text_color": forms.TextInput(attrs={"type": "color"}),
            "overlay_color": forms.TextInput(attrs={"type": "color"}),
            "overlay_opacity": forms.NumberInput(attrs={"min": 0, "max": 100}),
        }


class NewsImageInline(admin.TabularInline):
    model = NewsImage
    extra = 0
    max_num = 3
    fields = ("preview", "image", "caption", "sort")
    readonly_fields = ("preview",)

    def preview(self, obj):
        if obj and obj.image:
            return format_html('<img src="{}" style="height:46px;border-radius:10px;" />', obj.image.url)
        return "—"
    preview.short_description = "Превью"


@admin.register(NewsPost)
class NewsPostAdmin(admin.ModelAdmin):
    form = NewsPostAdminForm

    list_display = ("id", "title", "is_published", "published_at", "card_style", "font_family", "cover_preview")
    list_filter = ("is_published", "card_style", "font_family")
    search_fields = ("title", "card_title", "body", "badge")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
    inlines = (NewsImageInline,)

    fields = (
        "title", "card_title", "slug",
        "is_published", "published_at",
        "card_style", "badge",
        "cover", "body",
        "font_family", "text_color",
        "overlay_style", "overlay_color", "overlay_opacity",
    )

    def cover_preview(self, obj):
        if obj.cover:
            return format_html('<img src="{}" style="height:46px;border-radius:10px;" />', obj.cover.url)
        return "—"
    cover_preview.short_description = "Обложка"
