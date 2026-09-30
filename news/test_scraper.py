import contextlib
import csv
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup
from django.test import SimpleTestCase, TestCase

from scraper import configs
from scraper.scraper import clean_text, detect_language, get_content, news_collect, scrape_article
from news.models import News


ARTICLE_HTML = """<html><h1>Fixture newspaper headline</h1><article class="article-content">
<header><span class="author-name">Reporter Name</span><time datetime="2026-10-01T09:30:00Z">Today</time></header>
<p>First reported paragraph with verified source material and a named source.</p>
<p>First reported paragraph with verified source material and a named source.</p>
<aside><p>This unrelated promotional text must not be extracted.</p></aside>
<p>Second reported paragraph containing further details for a complete article.</p>
<p>The programme will provide training for students and publish its progress in a public report.</p>
<img src="/images/story.jpg"></article></html>"""


def fixture_page(html=ARTICLE_HTML, status=200):
    page = Mock()
    page.goto.return_value = SimpleNamespace(status=status)
    page.content.return_value = html
    return page


class ParserTests(SimpleTestCase):
    def test_all_configured_parsers_preserve_metadata_and_clean_content(self):
        for config in (configs.DAILY_STAR_CONFIG, configs.DHAKA_TRIBUNE_CONFIG,
                       configs.BUSINESS_STANDARD_CONFIG, configs.DAILY_SUN_CONFIG):
            with self.subTest(config=config):
                data = scrape_article(fixture_page(), "https://example.com/news/story", config)
                self.assertEqual(data["Title"], "Fixture newspaper headline")
                self.assertEqual(data["Author"], "Reporter Name")
                self.assertEqual(data["Published_Date"], "2026-10-01T09:30:00Z")
                self.assertEqual(data["Image_URL"], "https://example.com/images/story.jpg")
                self.assertNotIn("promotional", data["Content"])
                self.assertEqual(data["Content"].count("First reported"), 1)

    def test_error_pages_and_empty_layouts_are_not_saved_as_articles(self):
        with contextlib.redirect_stdout(io.StringIO()):
            for status in (403, 404, 429, 503):
                with self.subTest(status=status):
                    page = fixture_page(status=status)
                    self.assertIsNone(scrape_article(page, "https://example.com/story", configs.DAILY_STAR_CONFIG))
                    page.content.assert_not_called()
            self.assertIsNone(scrape_article(fixture_page("<h1>Empty layout</h1>"),
                                             "https://example.com/story", configs.DAILY_STAR_CONFIG))

    def test_missing_image_and_bangla_text_are_preserved(self):
        html = "<h1>বাংলা সংবাদ শিরোনাম</h1><article><p>এটি বাংলাদেশের একটি সংবাদ প্রতিবেদন। তথ্য যাচাই করা হয়েছে।</p></article>"
        item = scrape_article(fixture_page(html), "https://example.com/story", configs.DAILY_STAR_CONFIG)
        self.assertEqual(item["Image_URL"], "")
        self.assertEqual(item["Language"], "Bangla")
        self.assertEqual(clean_text(" বাংলা\n সংবাদ  "), "বাংলা সংবাদ")
        self.assertEqual(detect_language("English source story"), "English")

    def test_cleaning_does_not_mutate_source_document(self):
        soup = BeautifulSoup(ARTICLE_HTML, "html.parser")
        get_content(soup, ["article"])
        self.assertIsNotNone(soup.select_one("header .author-name"))


CSV_FIELDS = ["source", "category", "title", "url", "content", "author", "published_date",
              "image_url", "language", "scraped_date"]
CATEGORY_HTML = """<main>
<h2><a href="/story">A sufficiently long headline</a></h2>
<h2><a href="/story#details">A duplicate story link with fragment</a></h2>
<h2><a href="https://other.example/story">An external source to ignore</a></h2>
<h2><a href="mailto:reporter@example.com">Contact the newspaper reporter</a></h2>
</main>"""


def collect_fixture(path):
    category_page, article_page = fixture_page(CATEGORY_HTML), fixture_page()
    with patch("scraper.scraper.sync_playwright") as playwright, contextlib.redirect_stdout(io.StringIO()):
        browser = playwright.return_value.__enter__.return_value.chromium.launch.return_value
        browser.new_page.side_effect = [category_page, article_page]
        count = news_collect(["news", "other"], "https://example.com", "Fixture",
                             configs.DAILY_STAR_CONFIG, str(path))
        browser.close.assert_called_once()
    return count, article_page


class CollectorTests(TestCase):
    def test_category_fragments_external_links_and_reruns_do_not_duplicate_articles(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "news.csv"
            count, article_page = collect_fixture(output)
            self.assertEqual(count, 1)
            self.assertEqual(News.objects.count(), 1)
            article_page.goto.assert_called_once()
            self.assertEqual(News.objects.get().url, "https://example.com/story")
            count, article_page = collect_fixture(output)
            self.assertEqual(count, 0)
            article_page.goto.assert_not_called()
            with output.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["url"], News.objects.get().url)

    def test_export_failure_is_recoverable_without_scraping_existing_articles(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "news.csv"
            with patch("scraper.database.write_csv_atomic", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    collect_fixture(output)
            self.assertEqual(News.objects.count(), 1)
            self.assertFalse(output.exists())
            count, article_page = collect_fixture(output)
            self.assertEqual(count, 0)
            article_page.goto.assert_not_called()
            with output.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0]), set(CSV_FIELDS))
            self.assertEqual(rows[0]["title"], News.objects.get().title)

    def test_existing_csv_records_survive_database_export(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "news.csv"
            original = dict.fromkeys(CSV_FIELDS, "")
            original.update(url="https://archive.example/story", title="Archived source article")
            with output.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
                writer.writeheader()
                writer.writerow(original)
            collect_fixture(output)
            with output.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0], original)
