import csv
import json
import random
import re
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
FINAL_DIR = BASE_DIR / "final"

INPUT_CSV = FINAL_DIR / "musinsa_reviews_all.csv"
OUTPUT_CSV = FINAL_DIR / "musinsa_reviews_clean.csv"
OUTPUT_JSONL = FINAL_DIR / "musinsa_reviews_clean.jsonl"

MIN_CONTENT_LENGTH = 5
MAX_REVIEWS_PER_PRODUCT = 100
RANDOM_SEED = 42

NEGATIVE_KEYWORDS = [
    "작", "크", "별로", "아쉽", "얇", "두껍", "불편", "불만",
    "환불", "반품", "다름", "달라", "실망", "구김", "비침",
    "타이트", "헐렁", "찢", "냄새", "거칠", "불량",
]

SIZE_NEGATIVE_VALUES = {"작음", "조금 작음", "큼", "조금 큼", "매우 큼", "매우 작음"}
COLOR_NEGATIVE_VALUES = {"화면과 다름", "조금 다름"}
THICKNESS_NEGATIVE_VALUES = {"얇음", "매우 얇음"}


def read_csv_rows(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} 파일이 없습니다.")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_too_short(text: str) -> bool:
    return len(text) < MIN_CONTENT_LENGTH


def has_negative_signal(row: dict[str, Any]) -> bool:
    content = normalize_text(str(row.get("content", ""))).lower()
    rating_raw = str(row.get("rating", "")).strip()

    try:
        rating = int(float(rating_raw))
    except Exception:
        rating = None

    if rating is not None and rating <= 3:
        return True

    survey_size = str(row.get("survey_size", "")).strip()
    survey_color = str(row.get("survey_color", "")).strip()
    survey_thickness = str(row.get("survey_thickness", "")).strip()

    if survey_size in SIZE_NEGATIVE_VALUES:
        return True
    if survey_color in COLOR_NEGATIVE_VALUES:
        return True
    if survey_thickness in THICKNESS_NEGATIVE_VALUES:
        return True

    for kw in NEGATIVE_KEYWORDS:
        if kw in content:
            return True

    return False


def basic_clean(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []

    for row in rows:
        content = normalize_text(str(row.get("content", "")))
        if not content:
            continue
        if is_too_short(content):
            continue

        row = dict(row)
        row["content"] = content
        cleaned.append(row)

    return cleaned


def deduplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # 1차: goods_no + review_id
    seen_id = set()
    dedup_1 = []

    for row in rows:
        key = (
            str(row.get("goods_no", "")).strip(),
            str(row.get("review_id", "")).strip(),
        )
        if key in seen_id:
            continue
        seen_id.add(key)
        dedup_1.append(row)

    # 2차: goods_no + normalized_content
    seen_text = set()
    dedup_2 = []

    for row in dedup_1:
        key = (
            str(row.get("goods_no", "")).strip(),
            normalize_text(str(row.get("content", ""))),
        )
        if key in seen_text:
            continue
        seen_text.add(key)
        dedup_2.append(row)

    return dedup_2


def limit_reviews_per_product(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    random.seed(RANDOM_SEED)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        goods_no = str(row.get("goods_no", "")).strip()
        grouped.setdefault(goods_no, []).append(row)

    final_rows = []

    for goods_no, group in grouped.items():
        if len(group) <= MAX_REVIEWS_PER_PRODUCT:
            final_rows.extend(group)
            continue

        negative_rows = [r for r in group if has_negative_signal(r)]
        normal_rows = [r for r in group if not has_negative_signal(r)]

        if len(negative_rows) >= MAX_REVIEWS_PER_PRODUCT:
            sampled = random.sample(negative_rows, MAX_REVIEWS_PER_PRODUCT)
            final_rows.extend(sampled)
            continue

        remaining_slots = MAX_REVIEWS_PER_PRODUCT - len(negative_rows)

        if len(normal_rows) > remaining_slots:
            normal_rows = random.sample(normal_rows, remaining_slots)

        final_rows.extend(negative_rows + normal_rows)

    return final_rows


def keep_final_columns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted_columns = [
        "goods_no",
        "review_id",
        "content",
        "rating",
        "created_at",
        "product_url",
        "source_categories",
        "option_text",
        "brand_name",
        "goods_name",
        "review_type",
        "review_type_name",
        "review_sex",
        "user_height",
        "user_weight",
        "user_level",
        "survey_size",
        "survey_color",
        "survey_thickness",
        "survey_stretch",
        "raw_json",
    ]

    output = []
    for row in rows:
        new_row = {col: row.get(col, "") for col in wanted_columns}
        output.append(new_row)

    return output


def save_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    if not rows:
        print("저장할 CSV 행이 없습니다.")
        return

    output_path.parent.mkdir(exist_ok=True)

    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_jsonl(rows: list[dict[str, Any]], output_path: Path) -> None:
    if not rows:
        print("저장할 JSONL 행이 없습니다.")
        return

    output_path.parent.mkdir(exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    rows = read_csv_rows(INPUT_CSV)
    print(f"원본 행 수: {len(rows)}")

    rows = basic_clean(rows)
    print(f"기본 정리 후 행 수: {len(rows)}")

    rows = deduplicate_rows(rows)
    print(f"중복 제거 후 행 수: {len(rows)}")

    rows = limit_reviews_per_product(rows)
    print(f"상품당 최대 리뷰 수 제한 후 행 수: {len(rows)}")

    rows = keep_final_columns(rows)
    print(f"최종 컬럼 정리 후 행 수: {len(rows)}")

    save_csv(rows, OUTPUT_CSV)
    save_jsonl(rows, OUTPUT_JSONL)

    print("\n정제 완료")
    print(f"CSV 저장: {OUTPUT_CSV}")
    print(f"JSONL 저장: {OUTPUT_JSONL}")


if __name__ == "__main__":
    main()