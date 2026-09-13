from Daily_Star import dailystar_base_url, dailystar_categories

from Dhaka_Tribune import dhakatribune_base_url, dhakatribune_categories

from The_Business_Standard import theBusinessStandard_categories,theBusinessStandard_base_url

from Daily_Sun import dailysun_base_url,dailysun_categories

from Scraper import news_collect

if __name__ == "__main__":
    csv_file = "news_data.csv"

    # Daily Star 
    news_collect(
        dailystar_categories,
        dailystar_base_url, 
        "The Daily Star", 
        csv_file,
    )

    # Dhaka Tribune
    news_collect(
        dhakatribune_categories,
        dhakatribune_base_url,
        "Dhaka Tribune",
        csv_file,
    )

    #The Business Standard
    news_collect(
            theBusinessStandard_categories,
            theBusinessStandard_base_url,
            "The Buisness Standard",
            csv_file,
        )
    # #Daily Sun
    # news_collect(
    #             dailysun_categories,
    #             dailysun_base_url,
    #             "Daily Sun",
    #             csv_file,
    #         )




    print(f"\nAll news successfully extracted and saved to '{csv_file}'!")