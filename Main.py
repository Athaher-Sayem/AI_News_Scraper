# from Daily_Star import dailystar_base_url, dailystar_categories
# from Dhaka_Tribune import dhakatribune_base_url, dhakatribune_categories
# from The_Business_Standard import (
#     theBusinessStandard_categories,
#     theBusinessStandard_base_url,
# )
# from Daily_Sun import dailysun_base_url, dailysun_categories
# from Scraper import news_collect


# if __name__ == "__main__":

#     csv_file = "news_data.csv"

#     # Daily Star
#     daily_star_count = news_collect(
#         dailystar_categories,
#         dailystar_base_url,
#         "The Daily Star",
#         csv_file,
#     )

#     print(f"\nThe Daily Star: {daily_star_count} new titles collected.")

#     # Dhaka Tribune
#     dhaka_tribune_count = news_collect(
#         dhakatribune_categories,
#         dhakatribune_base_url,
#         "Dhaka Tribune",
#         csv_file,
#     )

#     print(f"\nDhaka Tribune: {dhaka_tribune_count} new titles collected.")

#     # The Business Standard
#     business_standard_count = news_collect(
#         theBusinessStandard_categories,
#         theBusinessStandard_base_url,
#         "The Business Standard",
#         csv_file,
#     )

#     print(
#         f"\nThe Business Standard: "
#         f"{business_standard_count} new titles collected."
#     )

#     # Daily Sun
#     # daily_sun_count = news_collect(
#     #     dailysun_categories,
#     #     dailysun_base_url,
#     #     "Daily Sun",
#     #     csv_file,
#     # )

#     # Total new titles
#     total = (
#         daily_star_count
#         + dhaka_tribune_count
#         + business_standard_count
#     )

#     print("\n===================================")
#     print(f"TOTAL NEW TITLES COLLECTED: {total}")
#     print("===================================")

#     print(f"\nAll news successfully extracted and saved to '{csv_file}'!")


from scraper.scraper import news_collect

from scraper.configs import (
    DAILY_STAR_CONFIG,
    DHAKA_TRIBUNE_CONFIG,
    BUSINESS_STANDARD_CONFIG,
    DAILY_SUN_CONFIG,
)

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
    "news_data.csv",
)


# ============================================================
# DHAKA TRIBUNE
# ============================================================

news_collect(
    dhakatribune_categories,
    dhakatribune_base_url,
    "Dhaka Tribune",
    DHAKA_TRIBUNE_CONFIG,
    "news_data.csv",
)


# ============================================================
# THE BUSINESS STANDARD
# ============================================================

news_collect(
    theBusinessStandard_categories,
    theBusinessStandard_base_url,
    "The Business Standard",
    BUSINESS_STANDARD_CONFIG,
    "news_data.csv",
)


# ============================================================
# DAILY SUN
# ============================================================

news_collect(
    dailysun_categories,
    dailysun_base_url,
    "Daily Sun",
    DAILY_SUN_CONFIG,
    "news_data.csv",
)
