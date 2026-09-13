import csv
import re
import math
import random
import time
from collections import Counter, defaultdict

random.seed(42)


# CSV LOAD  (case-insensitive header + lowercase keys)

def load_titles(filepath):
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_lower = {(k or '').strip().lower(): v for k, v in row.items()}

            t = (row_lower.get('title') or '').strip()
            if t and len(t) > 10:
                data.append({
                    'source':   (row_lower.get('source')   or '').strip(),
                    'category': (row_lower.get('category') or '').strip(),
                    'title':    t,
                    'url':      (row_lower.get('url')      or '').strip(),
                })
    return data



# TEXT PREPROCESSING
STOPWORDS = {
    'the','a','an','and','or','but','in','on','at','to','for','of','with',
    'by','from','as','is','are','was','were','be','been','being','it','its',
    'this','that','these','those','has','have','had','will','would','can',
    'could','may','might','do','does','did','not','no','so','up','out','about',
    'after','before','over','under','into','through','during','between',
    'new','says','said','say','also','one','two','three','first','last',
    'amid','against','onto','upon','her','his','him','she','he','they',
    'their','them','we','our','you','your','i','me','my'
}


def tokenize(text):
    """Lowercase + punctuation remove + stopword remove + tokenize"""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    tokens = text.split()
    return [w for w in tokens if w not in STOPWORDS and len(w) > 1]


#  WORD2VEC 
class Word2Vec:

    def __init__(self, vector_size=100, window=3, negative_samples=5,
                 learning_rate=0.025, epochs=5):
        self.vector_size = vector_size
        self.window = window
        self.neg_samples = negative_samples
        self.lr = learning_rate
        self.epochs = epochs

        self.vocab = {}          
        self.idx2word = {}       
        self.word_counts = Counter()
        self.W_in = None
        self.W_out = None
        self.unigram_table = []

    # ---------- Vocab build ----------
    def build_vocab(self, tokenized_docs):
        for doc in tokenized_docs:
            self.word_counts.update(doc)

        vocab_words = [w for w, c in self.word_counts.items() if c >= 1]
        self.vocab = {w: i for i, w in enumerate(vocab_words)}
        self.idx2word = {i: w for w, i in self.vocab.items()}
        V = len(self.vocab)
        print(f"[Word2Vec] Vocab size: {V}")

      
        limit = 0.5 / self.vector_size
        self.W_in = [[random.uniform(-limit, limit) for _ in range(self.vector_size)]
                     for _ in range(V)]
        self.W_out = [[random.uniform(-limit, limit) for _ in range(self.vector_size)]
                      for _ in range(V)]

        total = sum(self.word_counts[w] ** 0.75 for w in self.vocab)
        self.unigram_table = []
        for w, c in self.word_counts.items():
            if w in self.vocab:
                prob = (c ** 0.75) / total
                self.unigram_table.extend([self.vocab[w]] * max(1, int(prob * 1_000_000)))

    # ---------- Helpers ----------
    @staticmethod
    def sigmoid(x):
        if x > 30:
            return 1.0
        if x < -30:
            return 0.0
        return 1.0 / (1.0 + math.exp(-x))

    def _dot(self, a, b):
        return sum(x * y for x, y in zip(a, b))

    def _negative_sample(self, exclude_idx, k):
        negs = []
        while len(negs) < k:
            idx = self.unigram_table[random.randint(0, len(self.unigram_table) - 1)]
            if idx != exclude_idx:
                negs.append(idx)
        return negs

    # ---------- Training ----------
    def train(self, tokenized_docs):
        lr0 = self.lr
        for epoch in range(self.epochs):
            
            self.lr = lr0 * (1.0 - epoch / self.epochs)
            total_loss = 0.0
            pairs = 0

            for doc in tokenized_docs:
                ids = [self.vocab[w] for w in doc if w in self.vocab]
                if len(ids) < 2:
                    continue
                for i, center in enumerate(ids):
                    win = random.randint(1, self.window)
                    start = max(0, i - win)
                    end = min(len(ids), i + win + 1)
                    for j in range(start, end):
                        if j == i:
                            continue
                        pairs += 1
                        total_loss += self._sgd_step(center, ids[j])

            avg_loss = total_loss / max(pairs, 1)
            print(f"[Word2Vec] Epoch {epoch+1}/{self.epochs} | "
                  f"Loss: {avg_loss:.4f} | LR: {self.lr:.4f}")

    def _sgd_step(self, center, context):
        """Proper forward → backward (gradients use SAME weights as forward)"""
        h = self.W_in[center]
        negs = self._negative_sample(context, self.neg_samples)
        targets = [context] + negs
        labels = [1.0] + [0.0] * self.neg_samples
        loss = 0.0

        
        cache = []
        for t_idx, label in zip(targets, labels):
            u = self.W_out[t_idx]
            score = self._dot(h, u)
            pred = self.sigmoid(score)
            err = pred - label
            cache.append((t_idx, err, u[:]))   
            loss += -(label * math.log(pred + 1e-9) +
                      (1 - label) * math.log(1 - pred + 1e-9))

        # ---------- Backward pass ----------
        grad_h = [0.0] * self.vector_size
        for t_idx, err, u_old in cache:
            for d in range(self.vector_size):
                grad_h[d] += err * u_old[d]                    # grad for W_in
                self.W_out[t_idx][d] -= self.lr * err * h[d]   # update W_out

        for d in range(self.vector_size):
            self.W_in[center][d] -= self.lr * grad_h[d]        # update W_in

        return loss

    # ---------- Get vectors ----------
    def get_vector(self, word):
        if word not in self.vocab:
            return None
        return self.W_in[self.vocab[word]]

    def doc_vector(self, tokens):
        """Document = average of its word vectors, L2-normalized"""
        vecs = [self.get_vector(w) for w in tokens if w in self.vocab]
        vecs = [v for v in vecs if v is not None]
        if not vecs:
            return [0.0] * self.vector_size

        avg = [0.0] * self.vector_size
        for v in vecs:
            for d in range(self.vector_size):
                avg[d] += v[d]
        for d in range(self.vector_size):
            avg[d] /= len(vecs)

        norm = math.sqrt(sum(x * x for x in avg)) or 1.0
        return [x / norm for x in avg]


#  TF-IDF VECTORIZER 

class TFIDFVectorizer:
    def __init__(self):
        self.vocab = {}
        self.idf = {}

    def fit_transform(self, tokenized_docs):
        vocab_set = set()
        for doc in tokenized_docs:
            vocab_set.update(doc)
        self.vocab = {w: i for i, w in enumerate(sorted(vocab_set))}
        N = len(tokenized_docs)

        df = Counter()
        for doc in tokenized_docs:
            for w in set(doc):
                df[w] += 1
        self.idf = {w: math.log((N + 1) / (df[w] + 1)) + 1 for w in self.vocab}

        vectors = []
        for doc in tokenized_docs:
            vec = [0.0] * len(self.vocab)
            tf = Counter(doc)
            total = len(doc) if doc else 1
            for w, c in tf.items():
                if w in self.vocab:
                    vec[self.vocab[w]] = (c / total) * self.idf[w]

            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vec = [v / norm for v in vec]
            vectors.append(vec)
        return vectors


#  SIMILARITY METRICS
def cosine(v1, v2):
    """Both already L2-normalized → dot product = cosine"""
    return sum(a * b for a, b in zip(v1, v2))


def jaccard(t1, t2):
    s1, s2 = set(t1), set(t2)
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


def hybrid_similarity(tok1, tok2, tfidf1, tfidf2, w2v1, w2v2,
                      alpha=0.4, beta=0.4, gamma=0.2):
    """
    alpha * TF-IDF cosine  (keyword match)
    beta  * Word2Vec cosine (semantic match)
    gamma * Jaccard         (exact token overlap)
    """
    s_tfidf = cosine(tfidf1, tfidf2)
    s_w2v = cosine(w2v1, w2v2)
    s_jac = jaccard(tok1, tok2)
    return alpha * s_tfidf + beta * s_w2v + gamma * s_jac



#  UNION-FIND CLUSTERING

class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[ry] = rx


def cluster_duplicates(sim_fn, n, threshold=0.55):
    uf = UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            if sim_fn(i, j) >= threshold:
                uf.union(i, j)
    groups = defaultdict(list)
    for i in range(n):
        groups[uf.find(i)].append(i)
    return list(groups.values())


#  REPRESENTATIVE TITLE SELECTION

def pick_representative(group, sim_matrix):
    if len(group) == 1:
        return group[0]
    best_idx, best_score = group[0], -1.0
    for i in group:
        s = sum(sim_matrix[i][j] for j in group if j != i)
        s /= (len(group) - 1)
        if s > best_score:
            best_score, best_idx = s, i
    return best_idx



# MAIN PIPELINE
def deduplicate(input_csv='news_data.csv',
                output_csv='deduped_news.csv',
                threshold=0.55,
                w2v_dim=100,
                w2v_epochs=5,
                w2v_window=3):

    t0 = time.time()

    # ---------- Load ----------
    print("=" * 60)
    print("STEP 1: Loading CSV")
    print("=" * 60)
    data = load_titles(input_csv)
    print(f"Loaded {len(data)} titles")
    if not data:
        print("No titles found. Check CSV header: source,category,title,url")
        return [], [], [], []

    # ---------- Tokenize ----------
    print("\n" + "=" * 60)
    print("STEP 2: Tokenizing")
    print("=" * 60)
    tokenized = [tokenize(d['title']) for d in data]
    print(f"Tokenized {len(tokenized)} documents")

    # ---------- Word2Vec ----------
    print("\n" + "=" * 60)
    print("STEP 3: Training Word2Vec (Skip-gram + Neg Sampling)")
    print("=" * 60)
    w2v = Word2Vec(vector_size=w2v_dim, window=w2v_window,
                   negative_samples=5, learning_rate=0.025,
                   epochs=w2v_epochs)
    w2v.build_vocab(tokenized)
    w2v.train(tokenized)
    w2v_doc_vecs = [w2v.doc_vector(toks) for toks in tokenized]

    # ---------- TF-IDF ----------
    print("\n" + "=" * 60)
    print("STEP 4: TF-IDF Vectorization")
    print("=" * 60)
    tfidf = TFIDFVectorizer()
    tfidf_doc_vecs = tfidf.fit_transform(tokenized)
    print(f"TF-IDF vocab size: {len(tfidf.vocab)}")

    # ---------- Similarity matrix ----------
    print("\n" + "=" * 60)
    print("STEP 5: Computing Similarity Matrix")
    print("=" * 60)
    n = len(data)
    sim_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        sim_matrix[i][i] = 1.0

    total_pairs = n * (n - 1) // 2
    done = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = hybrid_similarity(
                tokenized[i], tokenized[j],
                tfidf_doc_vecs[i], tfidf_doc_vecs[j],
                w2v_doc_vecs[i], w2v_doc_vecs[j]
            )
            sim_matrix[i][j] = s
            sim_matrix[j][i] = s
            done += 1
        # progress
        if (i + 1) % 50 == 0 or (i + 1) == n:
            pct = 100.0 * done / max(total_pairs, 1)
            print(f"  progress: {i+1}/{n} rows ({pct:.1f}%)")

    # ---------- Clustering ----------
    print("\n" + "=" * 60)
    print(f"STEP 6: Clustering (threshold={threshold})")
    print("=" * 60)
    groups = cluster_duplicates(lambda i, j: sim_matrix[i][j], n, threshold)
    groups = sorted(groups, key=lambda g: -len(g))
    print(f"Formed {len(groups)} clusters")

    # ---------- Representative selection ----------
    print("\n" + "=" * 60)
    print("STEP 7: Picking Representative Titles")
    print("=" * 60)
    kept, removed = [], []
    for g in groups:
        rep = pick_representative(g, sim_matrix)
        kept.append(data[rep])
        for idx in g:
            if idx != rep:
                removed.append((data[idx], data[rep]['title']))

    # ---------- Save (FIX: lowercase fieldnames matching load_titles) ----------
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=['source', 'category', 'title', 'url']
        )
        writer.writeheader()
        for row in kept:
            writer.writerow(row)

    # ---------- Report ----------
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"Original titles : {len(data)}")
    print(f"Kept (unique)   : {len(kept)}")
    print(f"Removed (dupes) : {len(removed)}")
    print(f"Output file     : {output_csv}")
    print(f"Elapsed time    : {time.time() - t0:.1f}s")

    print("\n--- Sample Duplicate Groups ---")
    shown = 0
    for g in groups:
        if len(g) > 1 and shown < 10:
            shown += 1
            rep_idx = pick_representative(g, sim_matrix)
            print(f"\n[Group of {len(g)}]")
            for idx in g:
                mark = "★" if idx == rep_idx else " "
                print(f"  {mark} {data[idx]['title']}")
                print(f"      ({data[idx]['source']} / {data[idx]['category']})")

    return kept, removed, groups, sim_matrix


# RUN

if __name__ == "__main__":
    deduplicate(
        input_csv='news_data.csv',
        output_csv='deduped_news.csv',
        threshold=0.55,
        w2v_dim=100,
        w2v_epochs=5,
        w2v_window=3
    )