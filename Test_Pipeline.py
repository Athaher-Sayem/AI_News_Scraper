from pipeline.news_pipeline import process_news


title = """
Bangladesh launches new technology initiative
"""


content = """
The government of Bangladesh announced a new
technology initiative in Dhaka on Monday.

The initiative will focus on developing digital
skills among young people.

Officials said the program will initially train
10,000 students.
"""


if __name__ == "__main__":
    result = process_news(title, content)

    print("\n==============================")
    print("FINAL RESULT")
    print("==============================")
    print("\nStatus:")
    print(result["status"])
    print("\nGenerated Article:")
    print(result.get("generated_article", ""))
    print("\nVerification:")
    print(result.get("verification", result.get("error", "")))
