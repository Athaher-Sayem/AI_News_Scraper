import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
import time
import re
import unicodedata
from pathlib import Path
from utils.csv_utils import write_csv_atomic


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "data" / "news_data.csv"
DEFAULT_OUTPUT = BASE_DIR / "data" / "unique_news.csv"


# LOAD DATA
def load_data(path=DEFAULT_INPUT):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.columns = [c.strip().lower() for c in df.columns]
    if "title" not in df.columns or df.columns.duplicated().any():
        raise ValueError("CSV requires a title column and unique normalized headers")
    df["title"] = df["title"].str.strip()
    df = df[df["title"].str.len() > 10].reset_index(drop=True)
    print(f"Loaded {len(df)} titles")
    return df


# 2. LIGHT PREPROCESSING (only for normalization, not stopword removal)


def normalize(text):
    text = unicodedata.normalize("NFC", text).lower()
    text = "".join(character if character.isspace() or unicodedata.category(character)[0] in "LNM"
                   else " " for character in text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# 3. HYBRID SIMILARITY: SBERT (semantic) + TF-IDF (keyword)


def compute_hybrid_similarity(titles, sbert_weight=0.7, tfidf_weight=0.3):
    """
    SBERT captures meaning, TF-IDF captures exact keyword overlap.
    """
    from sentence_transformers import SentenceTransformer

    # --- SBERT embeddings ---
    print("Loading Sentence-BERT model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print("Encoding titles with SBERT...")
    sbert_emb = model.encode(
        titles,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    sbert_sim = cosine_similarity(sbert_emb)

    # --- TF-IDF similarity ---
    print("Computing TF-IDF similarity...")
    tfidf = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
        sublinear_tf=True,
        stop_words="english",
    )
    try:
        tfidf_matrix = tfidf.fit_transform([normalize(t) for t in titles])
    except ValueError as error:
        # Identical headlines or non-English titles may leave no vocabulary
        # after pruning. Semantic similarity still provides a usable result.
        if "no terms remain" not in str(error) and "empty vocabulary" not in str(error):
            raise
        return sbert_sim
    tfidf_sim = cosine_similarity(tfidf_matrix)

    # --- Hybrid ---
    hybrid = sbert_weight * sbert_sim + tfidf_weight * tfidf_sim
    print(f"Similarity matrix: {hybrid.shape}")
    return hybrid


# 4. CLUSTERING (Agglomerative with precomputed distance)


def cluster_titles(sim_matrix, threshold=0.72):
    """
    Agglomerative clustering with cosine distance.
    distance = 1 - similarity
    """
    distance = 1.0 - sim_matrix
    np.fill_diagonal(distance, 0.0)
    distance = np.clip(distance, 0, 1)

    clusterer = AgglomerativeClustering(
        n_clusters=None,
        metric="precomputed",
        linkage="average",
        distance_threshold=1.0 - threshold,
    )
    labels = clusterer.fit_predict(distance)
    print(f"Formed {len(set(labels))} clusters")
    return labels


# 5. PICK REPRESENTATIVE TITLE PER CLUSTER


def pick_representatives(df, labels, sim_matrix):
    kept_rows = []
    group_summary = []

    for label in sorted(set(labels)):
        idxs = np.where(labels == label)[0]

        if len(idxs) == 1:
            kept_rows.append(idxs[0])
            continue

        # most central = highest avg similarity
        sub = sim_matrix[np.ix_(idxs, idxs)]
        avg_sim = sub.mean(axis=1)
        best_local = int(np.argmax(avg_sim))
        rep_idx = idxs[best_local]

        kept_rows.append(rep_idx)
        group_summary.append(
            {
                "rep": df.iloc[rep_idx]["title"],
                "members": [df.iloc[i]["title"] for i in idxs],
            }
        )

    return kept_rows, group_summary


# 6. MAIN PIPELINE


def deduplicate(
    input_csv=DEFAULT_INPUT, output_csv=DEFAULT_OUTPUT, threshold=0.73
):

    if Path(input_csv).resolve() == Path(output_csv).resolve() or (
        Path(output_csv).exists() and Path(input_csv).samefile(output_csv)
    ):
        raise ValueError("Input and output CSV paths must be different")
    if not 0 < threshold < 1:
        raise ValueError("threshold must be between 0 and 1")
    t0 = time.time()
    df = load_data(input_csv)

    if len(df) < 2:
        df_kept, groups = df.copy(), []
    else:
        sim = compute_hybrid_similarity(df["title"].tolist())
        labels = cluster_titles(sim, threshold=threshold)
        kept_idx, groups = pick_representatives(df, labels, sim)
        df_kept = df.iloc[kept_idx].reset_index(drop=True)

    write_csv_atomic(df_kept, output_csv, encoding="utf-8")

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"Original : {len(df)}")
    print(f"Kept     : {len(df_kept)}")
    print(f"Removed  : {len(df) - len(df_kept)}")
    print(f"Time     : {time.time() - t0:.1f}s")
    print(f"Output   : {output_csv}")

    print("\n--- Sample Duplicate Groups ---")
    for g in groups[:8]:
        print(f"\n[Group of {len(g['members'])}]")
        print(f"  * {g['rep']}")
        for m in g["members"]:
            if m != g["rep"]:
                print(f"    - {m}")

    return df_kept, groups


if __name__ == "__main__":
    deduplicate()
