import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.utils import timezone

from news import spa
from .models import ArticleView, News


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
        (self.dist / "favicon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        assets = self.dist / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log('app')", encoding="utf-8")

    def read(self, response):
        content = b"".join(response.streaming_content)
        response.close()
        return content

    def test_missing_build_returns_helpful_503(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("npm run build", response.content.decode())

    def test_index_assets_and_client_routes(self):
        self.write_build()
        index = self.client.get("/")
        self.assertEqual(index.status_code, 200)
        self.assertIn("text/html", index["Content-Type"])
        self.assertIn(b"id=root", self.read(index))

        asset = self.client.get("/assets/app.js")
        self.assertEqual(asset.status_code, 200)
        self.assertIn("javascript", asset["Content-Type"])
        self.assertIn(b"app", self.read(asset))

        # Unknown client-side route falls back to index.html.
        client_route = self.client.get("/section/business")
        self.assertEqual(client_route.status_code, 200)
        self.assertIn(b"id=root", self.read(client_route))

    def test_traversal_outside_the_build_is_rejected(self):
        self.write_build()
        secret = self.dist.parent / "secret.txt"
        secret.write_text("do not serve", encoding="utf-8")
        self.addCleanup(secret.unlink)
        with self.assertRaises(Http404):
            spa.spa(RequestFactory().get("/"), path="../secret.txt")

    def test_specific_routes_are_not_captured_by_the_spa(self):
        self.write_build()
        # Admin and API routes must resolve before the catch-all SPA route.
        self.assertNotEqual(self.client.get("/api/v1/health/").status_code, 503)
        self.assertEqual(self.client.get("/collected/").status_code, 200)

    def test_unknown_api_routes_return_json_404_not_the_spa(self):
        self.write_build()
        for path in ("/api/v1/does-not-exist/", "/api/unknown", "/api/v1/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertIn("application/json", response["Content-Type"])
                self.assertEqual(response.json()["error"]["code"], "not_found")
                self.assertNotIn(b"id=root", response.content)

    def test_valid_spa_routes_still_serve_the_app(self):
        self.write_build()
        for path in ("/", "/section/business", "/article/1", "/search",
                     "/trending", "/about", "/contact", "/unknown-client-route"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"id=root", self.read(response))

    def test_post_is_not_allowed(self):
        self.write_build()
        self.assertEqual(self.client.post("/").status_code, 405)

    def test_missing_assets_404_but_real_assets_and_routes_work(self):
        self.write_build()
        ico = self.client.get("/favicon.ico")
        self.assertEqual(ico.status_code, 404)
        self.assertNotIn(b"id=root", ico.content)

        favicon = self.client.get("/favicon.svg")
        self.assertEqual(favicon.status_code, 200)
        self.assertIn("image/svg", favicon["Content-Type"])
        self.read(favicon)

        self.assertEqual(self.client.get("/assets/missing.js").status_code, 404)
        self.assertEqual(self.client.get("/assets/missing.css").status_code, 404)

        # Extensionless client routes still serve the app.
        route = self.client.get("/about")
        self.assertEqual(route.status_code, 200)
        self.assertIn(b"id=root", self.read(route))


class SeoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_robots_and_sitemap_are_served_without_the_spa(self):
        News.objects.create(source="Fixture", category="business", title="Seo story",
                            url="https://example.com/seo-1", content="Source text")
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn("text/plain", robots["Content-Type"])
        self.assertIn("Sitemap:", robots.content.decode())

        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn("application/xml", sitemap["Content-Type"])
        body = sitemap.content.decode()
        self.assertIn("/section/business", body)
        self.assertIn(f"/article/{News.objects.get().pk}", body)

    def test_sitemap_is_valid_cached_and_refreshes_when_data_changes(self):
        from xml.etree import ElementTree

        first = News.objects.create(source="Fixture", category="business", title="First",
                                    url="https://example.com/seo-a", content="Source text")
        body = self.client.get("/sitemap.xml").content.decode()
        ElementTree.fromstring(body)
        self.assertIn(f"/article/{first.pk}", body)
        self.assertRegex(body, r"<lastmod>\d{4}-\d{2}-\d{2}</lastmod>")

        # The second identical request is served from cache.
        self.assertEqual(body, self.client.get("/sitemap.xml").content.decode())

        # Adding an article changes the cache key and refreshes the sitemap.
        second = News.objects.create(source="Fixture", category="business", title="Second",
                                     url="https://example.com/seo-b", content="Source text")
        refreshed = self.client.get("/sitemap.xml").content.decode()
        self.assertIn(f"/article/{second.pk}", refreshed)
        self.assertNotEqual(body, refreshed)


class ArticleViewPruningTests(TestCase):
    def test_prune_removes_old_views_and_keeps_recent(self):
        article = News.objects.create(source="Fixture", category="business", title="Prune",
                                      url="https://example.com/prune", content="Source text")
        old = ArticleView.objects.create(article=article, client_key="old")
        recent = ArticleView.objects.create(article=article, client_key="recent")
        ArticleView.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=100))

        call_command("prune_article_views", "--days", "90")

        self.assertFalse(ArticleView.objects.filter(pk=old.pk).exists())
        self.assertTrue(ArticleView.objects.filter(pk=recent.pk).exists())

    def test_prune_rejects_non_positive_days(self):
        with self.assertRaises(CommandError):
            call_command("prune_article_views", "--days", "0")
