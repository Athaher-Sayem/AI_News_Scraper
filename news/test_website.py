from django.test import TestCase
from django.urls import reverse

from .models import News


class WebsiteTests(TestCase):
    def create_article(self, index=1, **kwargs):
        fields = dict(title=f"Article {index}", url=f"https://example.com/{index}", source="Fixture",
                      category="technology", language="English", content="Source excerpt. " * 120)
        fields.update(kwargs)
        return News.objects.create(**fields)

    def test_empty_collection_and_detail_404(self):
        self.assertContains(self.client.get("/"), "No stories match")
        self.assertEqual(self.client.get("/articles/99999/").status_code, 404)

    def test_search_category_and_language_filters(self):
        self.create_article(title="Technology announcement")
        bengali = self.create_article(2, title="বাংলা সংবাদ", category="education", language="Bangla")
        response = self.client.get("/", {"q": "বাংলা", "category": "education", "language": "Bangla"})
        self.assertContains(response, bengali.title)
        self.assertNotContains(response, "Technology announcement")
        detail = self.client.get(reverse("news:detail", args=[bengali.pk]))
        self.assertContains(detail, bengali.url)
        self.assertContains(detail, "not an approved newspaper publication")

    def test_pagination_keeps_filters_and_handles_bad_page_numbers(self):
        for index in range(14):
            self.create_article(index)
        first = self.client.get("/", {"category": "technology"})
        self.assertEqual(len(first.context["page"]), 12)
        self.assertContains(first, "category=technology&amp;page=2")
        second = self.client.get("/", {"category": "technology", "page": 2})
        self.assertEqual(len(second.context["page"]), 2)
        self.assertEqual(self.client.get("/", {"page": "invalid"}).status_code, 200)
        self.assertEqual(self.client.get("/", {"page": 10 ** 30}).status_code, 200)

    def test_source_text_is_escaped_and_existing_api_still_works(self):
        item = self.create_article(title='<script>alert("x")</script>')
        for path in ("/", reverse("news:detail", args=[item.pk])):
            response = self.client.get(path)
            self.assertNotContains(response, '<script>alert("x")</script>')
            self.assertContains(response, "&lt;script&gt;")
        api = self.client.get(f"/api/v1/articles/{item.pk}/")
        self.assertEqual(api.json()["data"]["title"], item.title)
