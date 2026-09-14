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

    def __str__(self):
        return self.title