from django.db import models

class News(models.Model):
    source = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000, unique=True)
    content = models.TextField(blank=True)
    author = models.CharField(max_length=300, blank=True)
    published_date = models.CharField(max_length=200, blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    language = models.CharField(max_length=20, blank=True)
    scraped_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["source"], name="news_source_idx"),
            models.Index(fields=["category"], name="news_category_idx"),
            models.Index(fields=["language"], name="news_language_idx"),
            models.Index(fields=["-scraped_date", "-id"], name="news_recent_idx"),
        ]

    def __str__(self):
        return self.title


class ArticleView(models.Model):
    """A single article open, recorded by the frontend beacon.

    This is a simple counter used to rank trending stories; it is not
    fraud-resistant and should be aggregated rather than trusted per row.
    """

    article = models.ForeignKey(News, on_delete=models.CASCADE, related_name="views")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["-created_at"], name="view_recent_idx"),
            models.Index(fields=["article", "-created_at"], name="view_article_idx"),
        ]

    def __str__(self):
        return f"View of {self.article_id} at {self.created_at:%Y-%m-%d %H:%M}"