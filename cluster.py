import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans

# ১. CSV লোড এবং ডুপ্লিকেট/ফাঁকা ডেটা বাদ দেওয়া
df = pd.read_csv("news_data.csv")
df.drop_duplicates(subset=["Title"], inplace=True)
df.dropna(subset=["Title"], inplace=True)
titles = df["Title"].tolist()

print(f"Total Unique Titles: {len(titles)}")

# ২. Sentence Transformers দিয়ে এম্বেডিংস তৈরি
print("Creating embeddings from headlines...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = embedding_model.encode(titles, show_progress_bar=True)

# ৩. ৫টি ক্লাস্টারে ভাগ করা (K-Means)
num_clusters = 5
kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
df["Cluster_ID"] = kmeans.fit_predict(embeddings)

# ৪. ফলাফল সংরক্ষণ করা
df.to_csv("clustered_news.csv", index=False)
print("\nClustering complete! Saved to clustered_news.csv\n")

# ৫. প্রতিটি ক্লাস্টারের খবরের নমুনা নিয়ে প্রম্পট প্রিন্ট করা
for cluster_id in range(num_clusters):
    samples = df[df["Cluster_ID"] == cluster_id]["Title"].head(5).tolist()

    prompt = f"""--- Cluster {cluster_id} Prompt ---
Here are some news headlines from a single topic cluster:
{chr(10).join(f"- {title}" for title in samples)}

Task: Provide a single short category name (1-3 words) that best describes all these news items.
Category:
"""
    print(prompt)
