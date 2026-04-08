from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from kiwipiepy import Kiwi
from matplotlib.backends.backend_pdf import PdfPages
from sklearn.feature_extraction.text import TfidfVectorizer

matplotlib.rcParams["font.family"] = "NanumGothic"
matplotlib.rcParams["axes.unicode_minus"] = False

BASE_DIR = Path(__file__).resolve().parent
CLEANED_DIR = BASE_DIR / "cleaned"
OUTPUT_DIR = BASE_DIR / "analysis_final"

INPUT_CSV = CLEANED_DIR / "musinsa_train_ready.csv"

REPORT_PATH = OUTPUT_DIR / "report.md"
CHARTS_PDF_PATH = OUTPUT_DIR / "charts.pdf"

TOP_K = 20
TOP_CATEGORY_K = 8
TOP_BRAND_K = 15
MIN_BRAND_REVIEW_COUNT = 100
MIN_TOKEN_LEN = 2
MIN_DF = 10
MAX_FEATURES = 5000

STOPWORDS = {
    "무신사", "제품", "상품", "구매", "사용", "후기", "리뷰",
    "정말", "진짜", "너무", "조금", "그냥", "아주", "완전", "느낌",
    "생각", "정도", "부분", "경우", "관련", "이번", "항상",
    "있음", "없음", "있고", "없고", "같음", "보임",
    "그리고", "그래서", "그런데", "또한", "근데",
    "입니다", "있어요", "같아요", "좋아요", "했어요", "됩니다",
    "이거", "이건", "그거", "그건", "저는", "제가",
    "ㅎㅎ", "ㅋㅋ", "ㅠㅠ", "ㅜㅜ"
}

POSITIVE_THRESHOLD = 4
NEGATIVE_THRESHOLD = 2


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_data(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} 파일이 없습니다.")
    return pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)


def normalize_text(text: object) -> str:
    if pd.isna(text):
        return ""
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


kiwi = Kiwi()


@lru_cache(maxsize=200000)
def tokenize_text(text: str) -> tuple[str, ...]:
    text = normalize_text(text).lower()
    if not text:
        return tuple()

    tokens = []
    for tok in kiwi.tokenize(text):
        form = tok.form.strip().lower()
        tag = tok.tag

        if not form:
            continue
        if len(form) < MIN_TOKEN_LEN:
            continue
        if form in STOPWORDS:
            continue

        # 전통적/안정적인 방향으로 명사 중심 + 영문/숫자 토큰 일부 허용
        if tag.startswith("N") or tag in {"SL", "SH"}:
            if re.fullmatch(r"[0-9]+", form):
                continue
            tokens.append(form)

    return tuple(tokens)


def tokens_to_bigrams(tokens: list[str]) -> list[str]:
    return [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]


def build_token_counter(texts: pd.Series) -> Counter:
    counter = Counter()
    for text in texts.fillna("").astype(str):
        counter.update(tokenize_text(text))
    return counter


def build_bigram_counter(texts: pd.Series) -> Counter:
    counter = Counter()
    for text in texts.fillna("").astype(str):
        tokens = list(tokenize_text(text))
        counter.update(tokens_to_bigrams(tokens))
    return counter


def compute_log_odds_ratio(
    counter_a: Counter,
    counter_b: Counter,
    top_k: int = TOP_K,
    alpha: float = 1.0,
) -> tuple[list[tuple[str, float, int, int]], list[tuple[str, float, int, int]]]:
    vocab = set(counter_a) | set(counter_b)
    total_a = sum(counter_a.values())
    total_b = sum(counter_b.values())

    positive_side = []
    negative_side = []

    for token in vocab:
        a = counter_a[token]
        b = counter_b[token]

        score = math.log((a + alpha) / (total_a + alpha * len(vocab))) - math.log(
            (b + alpha) / (total_b + alpha * len(vocab))
        )

        row = (token, score, a, b)

        if score > 0:
            negative_side.append(row)
        else:
            positive_side.append(row)

    negative_side.sort(key=lambda x: x[1], reverse=True)
    positive_side.sort(key=lambda x: x[1])

    # positive_side는 score가 더 음수일수록 positive 쪽 특징
    positive_side = [(t, -s, a, b) for t, s, a, b in positive_side[:top_k]]
    negative_side = negative_side[:top_k]

    return negative_side, positive_side


def compute_tfidf_keywords_by_group(
    df: pd.DataFrame,
    group_col: str,
    text_col: str = "content",
    top_group_k: int = TOP_CATEGORY_K,
    top_token_k: int = 15,
) -> dict[str, list[tuple[str, float]]]:
    work = df[[group_col, text_col]].copy()
    work[group_col] = work[group_col].fillna("").astype(str)
    work[text_col] = work[text_col].fillna("").astype(str)

    top_groups = work[group_col].value_counts().head(top_group_k).index.tolist()
    work = work[work[group_col].isin(top_groups)].copy()

    if work.empty:
        return {}

    vectorizer = TfidfVectorizer(
        tokenizer=lambda x: list(tokenize_text(x)),
        token_pattern=None,
        lowercase=False,
        min_df=MIN_DF,
        max_features=MAX_FEATURES,
    )
    X = vectorizer.fit_transform(work[text_col].tolist())
    vocab = vectorizer.get_feature_names_out()

    result: dict[str, list[tuple[str, float]]] = {}
    for group_name in top_groups:
        idx = work.index[work[group_col] == group_name].tolist()
        if not idx:
            continue

        row_positions = [work.index.get_loc(i) for i in idx]
        scores = X[row_positions].mean(axis=0).A1
        pairs = list(zip(vocab, scores))
        pairs.sort(key=lambda x: x[1], reverse=True)
        result[group_name] = pairs[:top_token_k]

    return result


def make_markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines)


def top_counter_rows(counter: Counter, top_k: int = TOP_K) -> list[list[object]]:
    return [[token, count] for token, count in counter.most_common(top_k)]


def tfidf_rows(pairs: list[tuple[str, float]]) -> list[list[object]]:
    return [[token, f"{score:.6f}"] for token, score in pairs]


def log_odds_rows(rows: list[tuple[str, float, int, int]]) -> list[list[object]]:
    return [[token, f"{score:.4f}", a, b] for token, score, a, b in rows]


def build_report(
    df: pd.DataFrame,
    all_counter: Counter,
    pos_counter: Counter,
    neg_counter: Counter,
    all_bigram: Counter,
    neg_bigram: Counter,
    neg_keywords: list[tuple[str, float, int, int]],
    pos_keywords: list[tuple[str, float, int, int]],
    category_tfidf: dict[str, list[tuple[str, float]]],
    brand_negative_df: pd.DataFrame,
) -> str:
    rating_num = pd.to_numeric(df["rating"], errors="coerce")

    lines = []
    lines.append("# Musinsa Review NLP Analysis Report")
    lines.append("")
    lines.append("## 1. Basic Summary")
    lines.append("")
    lines.append(
        make_markdown_table(
            ["Metric", "Value"],
            [
                ["rows", len(df)],
                ["unique_goods", df["goods_no"].nunique()],
                ["unique_reviews", df["review_id"].nunique()],
                ["mean_rating", f"{rating_num.mean():.4f}"],
                ["median_rating", f"{rating_num.median():.4f}"],
                ["positive_ratio_(>=4)", f"{((rating_num >= POSITIVE_THRESHOLD).mean() * 100):.2f}%"],
                ["negative_ratio_(<=2)", f"{((rating_num <= NEGATIVE_THRESHOLD).mean() * 100):.2f}%"],
                ["mean_content_length", f"{df['content_length'].mean():.2f}"],
                ["median_content_length", f"{df['content_length'].median():.2f}"],
            ],
        )
    )
    lines.append("")

    lines.append("## 2. Overall Top Tokens")
    lines.append("")
    lines.append(make_markdown_table(["Token", "Count"], top_counter_rows(all_counter)))
    lines.append("")

    lines.append("## 3. Positive Review Top Tokens")
    lines.append("")
    lines.append(make_markdown_table(["Token", "Count"], top_counter_rows(pos_counter)))
    lines.append("")

    lines.append("## 4. Negative Review Top Tokens")
    lines.append("")
    lines.append(make_markdown_table(["Token", "Count"], top_counter_rows(neg_counter)))
    lines.append("")

    lines.append("## 5. Overall Top Bigrams")
    lines.append("")
    lines.append(make_markdown_table(["Bigram", "Count"], top_counter_rows(all_bigram)))
    lines.append("")

    lines.append("## 6. Negative Review Top Bigrams")
    lines.append("")
    lines.append(make_markdown_table(["Bigram", "Count"], top_counter_rows(neg_bigram)))
    lines.append("")

    lines.append("## 7. Negative vs Positive Discriminative Keywords (Log-Odds)")
    lines.append("")
    lines.append("### 7-1. Negative-Side Keywords")
    lines.append("")
    lines.append(
        make_markdown_table(
            ["Token", "Score", "NegCount", "PosCount"],
            log_odds_rows(neg_keywords),
        )
    )
    lines.append("")
    lines.append("### 7-2. Positive-Side Keywords")
    lines.append("")
    lines.append(
        make_markdown_table(
            ["Token", "Score", "PosCount", "NegCount"],
            log_odds_rows(pos_keywords),
        )
    )
    lines.append("")

    lines.append("## 8. Category-Specific Keywords (TF-IDF)")
    lines.append("")
    for category, pairs in category_tfidf.items():
        lines.append(f"### {category}")
        lines.append("")
        lines.append(make_markdown_table(["Token", "Mean TF-IDF"], tfidf_rows(pairs)))
        lines.append("")

    lines.append("## 9. Brands with High Negative Review Ratio")
    lines.append("")
    if not brand_negative_df.empty:
        lines.append(
            make_markdown_table(
                ["Brand", "ReviewCount", "NegativeRatio(%)"],
                [
                    [row["brand_name"], int(row["review_count"]), f"{row['negative_ratio_pct']:.2f}"]
                    for _, row in brand_negative_df.iterrows()
                ],
            )
        )
    else:
        lines.append("조건을 만족하는 브랜드가 없습니다.")
    lines.append("")

    lines.append("## 10. Chart File")
    lines.append("")
    lines.append(f"- `{CHARTS_PDF_PATH.name}`")
    lines.append("")

    return "\n".join(lines)


def add_barh_page(pdf: PdfPages, labels: list[str], values: list[float], title: str, xlabel: str) -> None:
    if not labels:
        return
    plt.figure(figsize=(10, 7))
    plt.barh(labels[::-1], values[::-1])
    plt.xlabel(xlabel)
    plt.title(title)
    plt.tight_layout()
    pdf.savefig()
    plt.close()


def add_hist_page(pdf: PdfPages, series: pd.Series, bins: int, title: str, xlabel: str) -> None:
    plt.figure(figsize=(9, 6))
    series.plot(kind="hist", bins=bins)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.tight_layout()
    pdf.savefig()
    plt.close()


def build_charts(
    df: pd.DataFrame,
    all_counter: Counter,
    pos_counter: Counter,
    neg_counter: Counter,
    neg_bigram: Counter,
    brand_negative_df: pd.DataFrame,
) -> None:
    rating_num = pd.to_numeric(df["rating"], errors="coerce")
    with PdfPages(CHARTS_PDF_PATH) as pdf:
        add_hist_page(pdf, rating_num.dropna(), 10, "Rating Distribution", "Rating")
        add_hist_page(pdf, df["content_length"].clip(upper=300), 50, "Content Length Distribution (clipped at 300)", "Length")
        reviews_per_goods = df.groupby("goods_no").size().clip(upper=100)
        add_hist_page(pdf, reviews_per_goods, 50, "Reviews per Product Distribution (clipped at 100)", "Reviews per Product")

        add_barh_page(
            pdf,
            list(df["analysis_category"].value_counts().head(15).index),
            list(df["analysis_category"].value_counts().head(15).values),
            "Top Analysis Categories by Review Count",
            "Review Count",
        )

        add_barh_page(
            pdf,
            [t for t, _ in all_counter.most_common(TOP_K)],
            [c for _, c in all_counter.most_common(TOP_K)],
            "Top Overall Tokens",
            "Count",
        )

        add_barh_page(
            pdf,
            [t for t, _ in pos_counter.most_common(TOP_K)],
            [c for _, c in pos_counter.most_common(TOP_K)],
            "Top Positive Tokens",
            "Count",
        )

        add_barh_page(
            pdf,
            [t for t, _ in neg_counter.most_common(TOP_K)],
            [c for _, c in neg_counter.most_common(TOP_K)],
            "Top Negative Tokens",
            "Count",
        )

        add_barh_page(
            pdf,
            [t for t, _ in neg_bigram.most_common(TOP_K)],
            [c for _, c in neg_bigram.most_common(TOP_K)],
            "Top Negative Bigrams",
            "Count",
        )

        if not brand_negative_df.empty:
            add_barh_page(
                pdf,
                brand_negative_df["brand_name"].tolist(),
                brand_negative_df["negative_ratio_pct"].tolist(),
                "Top Brands by Negative Review Ratio",
                "Negative Ratio (%)",
            )


def main() -> None:
    ensure_output_dir()

    print(f"[LOAD] {INPUT_CSV}")
    df = load_data(INPUT_CSV)
    print(f"[LOADED] rows={len(df)} cols={len(df.columns)}")

    df = df.copy()
    df["content"] = df["content"].fillna("").astype(str).map(normalize_text)
    df["content_length"] = df["content"].str.len()
    df["rating_num"] = pd.to_numeric(df["rating"], errors="coerce")

    df_all = df
    df_positive = df[df["rating_num"] >= POSITIVE_THRESHOLD].copy()
    df_negative = df[df["rating_num"] <= NEGATIVE_THRESHOLD].copy()

    print(f"[SPLIT] all={len(df_all)} positive={len(df_positive)} negative={len(df_negative)}")

    all_counter = build_token_counter(df_all["content"])
    pos_counter = build_token_counter(df_positive["content"])
    neg_counter = build_token_counter(df_negative["content"])

    all_bigram = build_bigram_counter(df_all["content"])
    neg_bigram = build_bigram_counter(df_negative["content"])

    neg_keywords, pos_keywords = compute_log_odds_ratio(neg_counter, pos_counter)

    category_tfidf = compute_tfidf_keywords_by_group(
        df,
        group_col="analysis_category",
        text_col="content",
        top_group_k=TOP_CATEGORY_K,
        top_token_k=15,
    )

    brand_negative_df = (
        df.assign(is_negative=df["rating_num"] <= NEGATIVE_THRESHOLD)
        .groupby("brand_name")
        .agg(review_count=("brand_name", "size"), negative_ratio=("is_negative", "mean"))
        .reset_index()
    )
    brand_negative_df = brand_negative_df[brand_negative_df["brand_name"].fillna("").astype(str) != ""]
    brand_negative_df = brand_negative_df[brand_negative_df["review_count"] >= MIN_BRAND_REVIEW_COUNT].copy()
    brand_negative_df["negative_ratio_pct"] = brand_negative_df["negative_ratio"] * 100
    brand_negative_df = brand_negative_df.sort_values(
        ["negative_ratio_pct", "review_count"], ascending=[False, False]
    ).head(TOP_BRAND_K)

    report = build_report(
        df=df,
        all_counter=all_counter,
        pos_counter=pos_counter,
        neg_counter=neg_counter,
        all_bigram=all_bigram,
        neg_bigram=neg_bigram,
        neg_keywords=neg_keywords,
        pos_keywords=pos_keywords,
        category_tfidf=category_tfidf,
        brand_negative_df=brand_negative_df,
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"[DONE] report -> {REPORT_PATH}")

    build_charts(
        df=df,
        all_counter=all_counter,
        pos_counter=pos_counter,
        neg_counter=neg_counter,
        neg_bigram=neg_bigram,
        brand_negative_df=brand_negative_df,
    )
    print(f"[DONE] charts -> {CHARTS_PDF_PATH}")

    print(f"\n결과 폴더: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()