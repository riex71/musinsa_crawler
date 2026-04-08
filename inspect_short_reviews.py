from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "merged" / "all" / "musinsa_all_merged.csv"
OUTPUT_CSV = BASE_DIR / "analysis_final" / "short_reviews_le_5.csv"

MAX_LEN = 5


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"{INPUT_CSV} 파일이 없습니다.")

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig", low_memory=False)

    df["content"] = df["content"].fillna("").astype(str).str.strip()
    df["content_length"] = df["content"].str.len()

    short_df = df[df["content_length"] <= MAX_LEN].copy()

    keep_cols = [
        "goods_no",
        "review_id",
        "content",
        "content_length",
        "rating",
        "created_at",
        "brand_name",
        "goods_name",
        "source_big_category_name_ko",
        "source_small_category_name_ko_norm",
    ]
    keep_cols = [col for col in keep_cols if col in short_df.columns]
    short_df = short_df[keep_cols]

    short_df = short_df.sort_values(
        by=["content_length", "rating", "created_at"],
        ascending=[True, True, True],
        na_position="last",
    )

    short_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"전체 row 수: {len(df)}")
    print(f"{MAX_LEN}자 이하 리뷰 수: {len(short_df)}")
    print(f"저장 파일: {OUTPUT_CSV}")

    print("\n샘플 30개:")
    sample_cols = [c for c in ["content", "content_length", "rating", "brand_name", "source_small_category_name_ko_norm"] if c in short_df.columns]
    print(short_df[sample_cols].head(30).to_string(index=False))


if __name__ == "__main__":
    main()