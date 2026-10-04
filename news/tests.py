import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from news import spa
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


class SpaServingTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.dist = Path(self.directory.name)
        patcher = patch.object(spa, "DIST_DIR", self.dist)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_build(self):
        (self.dist / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
        assets = self.dist / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log('app')", encoding="utf-8")

    def test_missing_build_returns_helpful_503(self):
        response = self.client.get("/app/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("npm run build", response.content.decode())

    def read(self, response):
        content = b"".join(response.streaming_content)
        response.close()
        return content

    def test_index_assets_client_routes_and_traversal(self):
        self.write_build()
        index = self.client.get("/app/")
        self.assertEqual(index.status_code, 200)
        self.assertIn("text/html", index["Content-Type"])
        self.assertIn(b"id=root", self.read(index))

        asset = self.client.get("/app/assets/app.js")
        self.assertEqual(asset.status_code, 200)
        self.assertIn("javascript", asset["Content-Type"])
        self.assertIn(b"app", self.read(asset))

        # Unknown client-side route falls back to index.html.
        client_route = self.client.get("/app/section/business")
        self.assertEqual(client_route.status_code, 200)
        self.assertIn(b"id=root", self.read(client_route))

        # Directory traversal outside the build is rejected.
        secret = self.dist.parent / "secret.txt"
        secret.write_text("do not serve", encoding="utf-8")
        self.addCleanup(secret.unlink)
        traversal = self.client.get("/app/../secret.txt")
        self.assertEqual(traversal.status_code, 404)

    def test_post_is_not_allowed(self):
        self.write_build()
        self.assertEqual(self.client.post("/app/").status_code, 405)
