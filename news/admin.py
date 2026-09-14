from django.contrib import admin
from .models import News


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "source",
        "category",
        "language",
        "scraped_date",
    )

    list_filter = (
        "source",
        "category",
        "language",
    )

    search_fields = (
        "title",
        "content",
        "url",
    )

    ordering = (
        "-scraped_date",
    )