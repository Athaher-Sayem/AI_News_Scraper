from django.test import TestCase
from django.urls import reverse

from .models import News

HOME = "/collected/"


class WebsiteTests(TestCase):
    def test_unsafe_or_malformed_source_urls_are_not_rendered_as_links(self):
        for index, url in enumerate(("javascript:alert(1)", "data:text/html,script",
                                     "https://[invalid", "//example.com/story")):
            with self.subTest(url=url):
                article = self.create_article(index, url=url)
                response = self.client.get(reverse("news:detail", args=[article.pk]))
                self.assertContains(response, "original source link is unavailable")
                self.assertNotContains(response, 'class="source-link"')

    def create_article(self, index=1, **kwargs):
        fields = dict(title=f"Article {index}", url=f"https://example.com/{index}", source="Fixture",
                      category="technology", language="English", content="Source excerpt. " * 120)
        fields.update(kwargs)
        return News.objects.create(**fields)

    def test_empty_collection_and_detail_404(self):
        self.assertContains(self.client.get(HOME), "No stories match")
        self.assertEqual(self.client.get(reverse("news:detail", args=[99999])).status_code, 404)

    def test_search_category_and_language_filters(self):
        self.create_article(title="Technology announcement")
        bengali = self.create_article(2, title="বাংলা সংবাদ", category="education", language="Bangla")
        response = self.client.get(HOME, {"q": "বাংলা", "category": "education", "language": "Bangla"})
        self.assertContains(response, bengali.title)
        self.assertNotContains(response, "Technology announcement")
        detail = self.client.get(reverse("news:detail", args=[bengali.pk]))
        self.assertContains(detail, bengali.url)
        self.assertContains(detail, "not an approved newspaper publication")

    def test_pagination_keeps_filters_and_handles_bad_page_numbers(self):
        for index in range(14):
            self.create_article(index)
        first = self.client.get(HOME, {"category": "technology"})
        self.assertEqual(len(first.context["page"]), 12)
        self.assertContains(first, "category=technology&amp;page=2")
        second = self.client.get(HOME, {"category": "technology", "page": 2})
        self.assertEqual(len(second.context["page"]), 2)
        self.assertEqual(self.client.get(HOME, {"page": "invalid"}).status_code, 200)
        self.assertEqual(self.client.get(HOME, {"page": 10 ** 30}).status_code, 200)

    def test_unfiltered_pagination_links_omit_empty_query_separator(self):
        for index in range(14):
            self.create_article(index)
        first = self.client.get(HOME)
        self.assertContains(first, 'href="?page=2"')
        self.assertNotContains(first, "?&amp;page=2")
        second = self.client.get(HOME, {"page": 2})
        self.assertContains(second, 'href="?page=1"')
        self.assertNotContains(second, "?&amp;page=1")

    def test_source_text_is_escaped_and_existing_api_still_works(self):
        item = self.create_article(title='<script>alert("x")</script>')
        for path in (HOME, reverse("news:detail", args=[item.pk])):
            response = self.client.get(path)
            self.assertNotContains(response, '<script>alert("x")</script>')
            self.assertContains(response, "&lt;script&gt;")
        api = self.client.get(f"/api/v1/articles/{item.pk}/")
        self.assertEqual(api.json()["data"]["title"], item.title)
