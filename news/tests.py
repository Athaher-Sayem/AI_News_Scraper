from django.test import TestCase

from .models import News


class NewsIndexTests(TestCase):
    def test_filter_and_order_columns_are_indexed(self):
        indexed = {tuple(index.fields) for index in News._meta.indexes}
        self.assertIn(("source",), indexed)
        self.assertIn(("category",), indexed)
        self.assertIn(("language",), indexed)
        self.assertIn(("-scraped_date", "-id"), indexed)

    def test_indexed_columns_filter_and_order_correctly(self):
        News.objects.create(source="Daily Star", category="business", title="First",
                            url="https://example.com/first", language="English")
        News.objects.create(source="Dhaka Tribune", category="sport", title="Second",
                            url="https://example.com/second", language="Bangla")
        self.assertEqual(News.objects.filter(source="Daily Star").count(), 1)
        self.assertEqual(News.objects.filter(category="sport").count(), 1)
        self.assertEqual(News.objects.filter(language="Bangla").count(), 1)
        self.assertEqual(
            list(News.objects.order_by("-scraped_date", "-id").values_list("title", flat=True)),
            ["Second", "First"],
        )
