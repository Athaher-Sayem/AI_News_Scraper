from Scraper import news_collect
from Daily_Star import dailystar_categories,dailystar_base_url
from Dhaka_Tribune import dhakatribune_categories,dhakatribune_base_url



news_collect(dailystar_categories, dailystar_base_url, "The Daily Star")
news_collect(dhakatribune_categories, dhakatribune_base_url, "Dhaka Tribune")