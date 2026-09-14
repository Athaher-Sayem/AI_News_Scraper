from ai.fact_extractor import extract_facts
from ai.article_generator import generate_article


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


print("Extracting facts...")

facts = extract_facts(
    title,
    content
)


print("\nFacts:")
print(facts)


print("\nGenerating article...")

article = generate_article(
    title,
    content,
    facts
)


print("\nGenerated Article:")
print(article)