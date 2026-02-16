from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.urls import reverse


class NewsPostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True, published_at__lte=timezone.now())


class NewsPost(models.Model):
    class CardStyle(models.TextChoices):
        DEFAULT = "default", "Обычная"
        IMPORTANT = "important", "Важно"
        GIFT = "gift", "Подарок"
        MONTH = "month", "Месяц"

    class FontFamily(models.TextChoices):
        SYSTEM = "system", "Системный"
        INTER = "inter", "Inter"
        MONTSERRAT = "montserrat", "Montserrat"
        NUNITO = "nunito", "Nunito"
        PLAYFAIR = "playfair", "Playfair Display"

    class OverlayStyle(models.TextChoices):
        GRADIENT = "gradient", "Градиент снизу"
        SOLID = "solid", "Сплошная подложка"

    title = models.CharField("Заголовок (полный)", max_length=180)
    # ✅ то, что будет написано на карточке (как «ПОДАРОК», «ВАЖНО», «ДЕКАБРЬ»)
    card_title = models.CharField("Текст на карточке", max_length=30, blank=True)

    slug = models.SlugField("Слаг (URL)", max_length=220, unique=True, blank=True)

    # ✅ Обложка
    cover = models.ImageField("Обложка", upload_to="news/covers/%Y/%m/", blank=True, null=True)

    # ✅ Текст новости
    body = models.TextField("Текст", blank=True)

    # ✅ “Разнообразие”
    badge = models.CharField("Бейдж (необязательно)", max_length=30, blank=True)
    card_style = models.CharField("Стиль карточки", max_length=16, choices=CardStyle.choices, default=CardStyle.DEFAULT)

    # ✅ Настройки карточки (шрифт/цвета) из админки
    font_family = models.CharField("Шрифт карточки", max_length=16, choices=FontFamily.choices, default=FontFamily.SYSTEM)
    text_color = models.CharField("Цвет текста (HEX)", max_length=7, default="#FFFFFF")
    overlay_color = models.CharField("Цвет подложки (HEX)", max_length=7, default="#000000")
    overlay_style = models.CharField("Подложка", max_length=16, choices=OverlayStyle.choices, default=OverlayStyle.GRADIENT)
    overlay_opacity = models.PositiveIntegerField("Прозрачность подложки (%)", default=65)

    is_published = models.BooleanField("Опубликовано", default=True)
    published_at = models.DateTimeField("Дата публикации", default=timezone.now)

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    objects = NewsPostQuerySet.as_manager()

    class Meta:
        verbose_name = "Новость"
        verbose_name_plural = "Новости"
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["is_published", "published_at"], name="news_pub_idx"),
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self):
        return reverse("news:detail", kwargs={"slug": self.slug})

    @property
    def card_text(self) -> str:
        return (self.card_title or self.title or "").strip()

    @property
    def font_css(self) -> str:
        # можно расширять список без миграций
        mapping = {
            self.FontFamily.SYSTEM: 'system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
            self.FontFamily.INTER: '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
            self.FontFamily.MONTSERRAT: '"Montserrat", system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
            self.FontFamily.NUNITO: '"Nunito", system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
            self.FontFamily.PLAYFAIR: '"Playfair Display", Georgia, "Times New Roman", serif',
        }
        return mapping.get(self.font_family, mapping[self.FontFamily.SYSTEM])

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> str:
        s = (hex_color or "").strip().lstrip("#")
        if len(s) == 3:
            s = "".join([c * 2 for c in s])
        if len(s) != 6:
            return "0,0,0"
        try:
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            return f"{r},{g},{b}"
        except Exception:
            return "0,0,0"

    @property
    def overlay_rgb(self) -> str:
        return self._hex_to_rgb(self.overlay_color)

    @property
    def overlay_alpha(self) -> str:
        # например "0.65"
        return f"{max(0, min(100, int(self.overlay_opacity))) / 100:.2f}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "news"
            slug = base
            i = 2
            while NewsPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        # защита от неправильных процентов
        if self.overlay_opacity < 0:
            self.overlay_opacity = 0
        if self.overlay_opacity > 100:
            self.overlay_opacity = 100
        super().save(*args, **kwargs)


class NewsImage(models.Model):
    post = models.ForeignKey(NewsPost, verbose_name="Новость", on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("Фото", upload_to="news/photos/%Y/%m/")
    caption = models.CharField("Подпись (необязательно)", max_length=120, blank=True)
    sort = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Фото новости"
        verbose_name_plural = "Фото новости"
        ordering = ["sort", "id"]

    def __str__(self) -> str:
        return f"Фото для: {self.post_id}"
