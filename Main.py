import os
import django


# ============================================================
# DJANGO SETUP
# ============================================================

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

django.setup()


# ============================================================
# PROJECT PATH
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

CSV_PATH = os.path.join(
    BASE_DIR,
    "data",
    "news_data.csv",
)


# ============================================================
# IMPORT SCRAPER
# ============================================================

from scraper.scraper import news_collect


# ============================================================
# IMPORT CONFIGS
# ============================================================

from scraper.configs import (
    DAILY_STAR_CONFIG,
    DHAKA_TRIBUNE_CONFIG,
    BUSINESS_STANDARD_CONFIG,
    DAILY_SUN_CONFIG,
)


# ============================================================
# IMPORT SOURCES
# ============================================================

from sources.Daily_Star import (
    dailystar_base_url,
    dailystar_categories,
)

from sources.Dhaka_Tribune import (
    dhakatribune_base_url,
    dhakatribune_categories,
)

from sources.The_Business_Standard import (
    theBusinessStandard_base_url,
    theBusinessStandard_categories,
)

from sources.Daily_Sun import (
    dailysun_base_url,
    dailysun_categories,
)


# ============================================================
# DAILY STAR
# ============================================================

news_collect(
    dailystar_categories,
    dailystar_base_url,
    "Daily Star",
    DAILY_STAR_CONFIG,
    CSV_PATH,
)


# ============================================================
# DHAKA TRIBUNE
# ============================================================

news_collect(
    dhakatribune_categories,
    dhakatribune_base_url,
    "Dhaka Tribune",
    DHAKA_TRIBUNE_CONFIG,
    CSV_PATH,
)


# ============================================================
# THE BUSINESS STANDARD
# ============================================================

news_collect(
    theBusinessStandard_categories,
    theBusinessStandard_base_url,
    "The Business Standard",
    BUSINESS_STANDARD_CONFIG,
    CSV_PATH,
)


# ============================================================
# DAILY SUN
# ============================================================

news_collect(
    dailysun_categories,
    dailysun_base_url,
    "Daily Sun",
    DAILY_SUN_CONFIG,
    CSV_PATH,
)