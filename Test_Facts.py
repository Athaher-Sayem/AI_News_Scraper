from ai.fact_extractor import extract_facts


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
    facts = extract_facts(title, content)
    print(facts)
