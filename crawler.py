import csv
import json
import random
import re
import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_DIR = Path(__file__).resolve().parent
CATEGORIES_ROOT = BASE_DIR / "categories"
CATEGORY_MASTER_CSV = BASE_DIR / "category_master.csv"

API_URL = "https://goods.musinsa.com/api2/review/v1/view/list"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.musinsa.com/",
}

BATCH_SIZE = 100
MAX_REVIEWS_PER_PRODUCT = 100
TOTAL_CHUNKS = 8


def safe_get(d: dict, *keys, default: Any = None) -> Any:
    cur: Any = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def extract_goods_no(url: str) -> str | None:
    match = re.search(r"/products/(\d+)", url)
    return match.group(1) if match else None


def extract_survey_answer(survey_block: dict | None, attribute_name: str) -> str:
    if not isinstance(survey_block, dict):
        return ""

    questions = survey_block.get("questions")
    if not isinstance(questions, list):
        return ""

    for q in questions:
        if not isinstance(q, dict):
            continue
        if q.get("attribute") != attribute_name:
            continue

        answers = q.get("answers")
        if not isinstance(answers, list) or not answers:
            return ""

        first_answer = answers[0]
        if not isinstance(first_answer, dict):
            return ""

        return str(first_answer.get("answerShortText", "")).strip()

    return ""


def load_category_master(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} 파일이 없습니다.")

    rows: list[dict[str, str]] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            include_flag = str(row.get("include_for_project", "")).strip().upper()
            big_code = str(row.get("big_category_code", "")).strip()
            small_code = str(row.get("small_category_code", "")).strip()
            category_url = str(row.get("category_url", "")).strip()

            if include_flag != "Y":
                continue
            if not big_code or not small_code or not category_url:
                continue

            rows.append(
                {
                    "big_category_code": big_code,
                    "big_category_name_ko": str(row.get("big_category_name_ko", "")).strip(),
                    "small_category_code": small_code,
                    "small_category_name_ko_raw": str(row.get("small_category_name_ko_raw", "")).strip(),
                    "small_category_name_ko_norm": str(row.get("small_category_name_ko_norm", "")).strip(),
                    "category_url": category_url,
                }
            )

    rows.sort(key=lambda x: (x["big_category_code"], x["small_category_code"]))
    return rows


def build_chunks(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    if not rows:
        return []

    n = len(rows)
    base = n // TOTAL_CHUNKS
    rem = n % TOTAL_CHUNKS

    chunks: list[list[dict[str, str]]] = []
    start = 0

    for i in range(TOTAL_CHUNKS):
        size = base + (1 if i < rem else 0)
        if size <= 0:
            continue

        chunk = rows[start:start + size]
        if chunk:
            chunks.append(chunk)
        start += size

    return chunks


def choose_chunk(chunks: list[list[dict[str, str]]]) -> list[dict[str, str]]:
    total_chunks = len(chunks)

    print(f"전체 청크 수: {total_chunks}")
    for idx, chunk in enumerate(chunks, start=1):
        codes = [x["small_category_code"] for x in chunk]
        print(f"- 청크 {idx}: {codes[0]} ~ {codes[-1]} ({len(chunk)}개)")

    while True:
        raw = input(f"\n실행할 청크 번호를 입력하세요 (1~{total_chunks}): ").strip()

        if not raw.isdigit():
            print("숫자만 입력해주세요.")
            continue

        chunk_no = int(raw)
        if 1 <= chunk_no <= total_chunks:
            selected = chunks[chunk_no - 1]
            print(f"\n선택된 청크: {chunk_no}")
            print(f"포함 소분류 수: {len(selected)}")
            print(f"각 소분류당 이번 실행에서는 1배치(상품 {BATCH_SIZE}개)만 처리합니다.\n")
            return selected

        print("범위를 벗어났습니다.")


def get_small_dir(category_info: dict[str, str]) -> Path:
    return CATEGORIES_ROOT / category_info["big_category_code"] / category_info["small_category_code"]


def load_processed_goods(processed_file: Path) -> set[str]:
    if not processed_file.exists():
        return set()

    return {
        line.strip()
        for line in processed_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def append_line(file_path: Path, text: str) -> None:
    with file_path.open("a", encoding="utf-8") as f:
        f.write(text.rstrip("\n") + "\n")


def log_error(error_file: Path, message: str) -> None:
    append_line(error_file, message)


def load_product_entries(
    product_urls_file: Path,
    category_info: dict[str, str],
    error_file: Path,
) -> list[dict[str, Any]]:
    if not product_urls_file.exists():
        return []

    goods_map: dict[str, dict[str, Any]] = {}

    for raw_line in product_urls_file.read_text(encoding="utf-8").splitlines():
        url = raw_line.strip()
        if not url:
            continue

        goods_no = extract_goods_no(url)
        if not goods_no:
            log_error(error_file, f"[SKIP] goodsNo 추출 실패: {url}")
            continue

        if goods_no not in goods_map:
            goods_map[goods_no] = {
                "goods_no": goods_no,
                "product_url": url,
                "big_category_code": category_info["big_category_code"],
                "big_category_name_ko": category_info["big_category_name_ko"],
                "small_category_code": category_info["small_category_code"],
                "small_category_name_ko_raw": category_info["small_category_name_ko_raw"],
                "small_category_name_ko_norm": category_info["small_category_name_ko_norm"],
            }

    goods_list = list(goods_map.values())
    goods_list.sort(key=lambda x: x["goods_no"])
    return goods_list


def get_remaining_goods(goods_list: list[dict[str, Any]], processed_goods: set[str]) -> list[dict[str, Any]]:
    return [g for g in goods_list if g["goods_no"] not in processed_goods]


def select_batch(goods_list: list[dict[str, Any]], processed_goods: set[str]) -> list[dict[str, Any]]:
    remaining = get_remaining_goods(goods_list, processed_goods)
    return remaining[:BATCH_SIZE]


def normalize_review(review: dict, product_info: dict[str, Any], page: int) -> dict[str, Any]:
    content = (
        review.get("content")
        or review.get("reviewContent")
        or review.get("goodsOpinionContents")
        or ""
    )
    content = str(content).strip()

    review_id = (
        review.get("no")
        or review.get("reviewNo")
        or review.get("goodsOpinionNo")
        or ""
    )

    rating = (
        review.get("score")
        or review.get("grade")
        or review.get("point")
        or ""
    )

    created_at = (
        review.get("createDate")
        or review.get("regDate")
        or review.get("writeDate")
        or ""
    )

    option_text = (
        review.get("goodsOption")
        or review.get("optionName")
        or review.get("option")
        or ""
    )

    goods_raw = review.get("goods")
    goods = goods_raw if isinstance(goods_raw, dict) else {}

    user_profile_raw = review.get("userProfileInfo")
    user_profile = user_profile_raw if isinstance(user_profile_raw, dict) else {}

    survey_satisfaction_raw = review.get("reviewSurveySatisfaction")
    survey_satisfaction = survey_satisfaction_raw if isinstance(survey_satisfaction_raw, dict) else {}

    survey_repurchase_raw = review.get("reviewSurveyRepurchase")
    survey_repurchase = survey_repurchase_raw if isinstance(survey_repurchase_raw, dict) else {}

    return {
        "goods_no": product_info["goods_no"],
        "product_url": product_info["product_url"],
        "source_big_category_code": product_info["big_category_code"],
        "source_big_category_name_ko": product_info["big_category_name_ko"],
        "source_small_category_code": product_info["small_category_code"],
        "source_small_category_name_ko_raw": product_info["small_category_name_ko_raw"],
        "source_small_category_name_ko_norm": product_info["small_category_name_ko_norm"],
        "page": page,
        "review_id": str(review_id),
        "content": content,
        "rating": rating,
        "created_at": created_at,
        "option_text": option_text,
        "brand_name": goods.get("brandName", "") or "",
        "goods_name": goods.get("goodsName", "") or "",
        "goods_sex": goods.get("goodsSex", "") or "",
        "sale_status": goods.get("saleStatLabel", "") or "",
        "review_type": review.get("type", "") or "",
        "review_type_name": review.get("typeName", "") or "",
        "review_sub_type": review.get("subType", "") or "",
        "like_count": review.get("likeCount", 0) or 0,
        "comment_count": review.get("commentCount", 0) or 0,
        "comment_reply_count": review.get("commentReplyCount", 0) or 0,
        "is_first_review": review.get("isFirstReview", False),
        "channel_source": review.get("channelSource", "") or "",
        "channel_source_name": review.get("channelSourceName", "") or "",
        "user_id": review.get("userId", "") or review.get("memberId", "") or "",
        "encrypted_user_id": review.get("encryptedUserId", "") or "",
        "review_sex": user_profile.get("reviewSex", "") or "",
        "user_height": user_profile.get("userHeight", "") or "",
        "user_weight": user_profile.get("userWeight", "") or "",
        "user_level": user_profile.get("userLevel", "") or "",
        "survey_size": extract_survey_answer(survey_satisfaction, "사이즈"),
        "survey_color": extract_survey_answer(survey_satisfaction, "화면 대비 색감"),
        "survey_thickness": extract_survey_answer(survey_satisfaction, "두께감"),
        "survey_stretch": extract_survey_answer(survey_satisfaction, "신축성"),
        "repurchase_intent": extract_survey_answer(survey_repurchase, "재구매 의사"),
        "raw_json": json.dumps(review, ensure_ascii=False),
    }


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def fetch_reviews_for_product(
    session: requests.Session,
    product_info: dict[str, Any],
    error_file: Path,
    sleep_range: tuple[float, float] = (0.8, 1.5),
) -> tuple[list[dict[str, Any]], bool]:
    all_rows: list[dict[str, Any]] = []
    page = 0

    while True:
        params = {
            "goodsNo": product_info["goods_no"],
            "page": page,
            "pageSize": 10,
        }

        try:
            response = session.get(API_URL, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            log_error(
                error_file,
                f"[ERROR] 요청 실패 | goods_no={product_info['goods_no']} | "
                f"page={page} | url={product_info['product_url']} | {e}",
            )
            return all_rows, False

        items_raw = safe_get(data, "data", "list", default=[])
        items = items_raw if isinstance(items_raw, list) else []

        page_info_raw = safe_get(data, "data", "page", default={})
        page_info = page_info_raw if isinstance(page_info_raw, dict) else {}

        if not items:
            return all_rows, True

        for item in items:
            if not isinstance(item, dict):
                continue

            row = normalize_review(item, product_info=product_info, page=page)
            if row["content"]:
                all_rows.append(row)

            if len(all_rows) >= MAX_REVIEWS_PER_PRODUCT:
                return all_rows, True

        total_pages = page_info.get("totalPages")
        current_page = page_info.get("page", page)
        page += 1

        if isinstance(total_pages, int) and page >= total_pages:
            return all_rows, True

        if isinstance(current_page, int) and isinstance(total_pages, int):
            if current_page >= total_pages - 1:
                return all_rows, True

        time.sleep(random.uniform(*sleep_range))


def deduplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []

    for row in rows:
        key = (row["goods_no"], row["review_id"], row["content"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


def get_next_batch_number(batches_dir: Path) -> int:
    batches_dir.mkdir(exist_ok=True)
    pattern = re.compile(r"musinsa_reviews_batch(\d+)\.csv$")

    existing_numbers = []
    for path in batches_dir.glob("musinsa_reviews_batch*.csv"):
        match = pattern.search(path.name)
        if match:
            existing_numbers.append(int(match.group(1)))

    return 1 if not existing_numbers else max(existing_numbers) + 1


def get_output_paths(batches_dir: Path, batch_number: int) -> tuple[Path, Path]:
    batch_tag = f"batch{batch_number:02d}"
    csv_path = batches_dir / f"musinsa_reviews_{batch_tag}.csv"
    jsonl_path = batches_dir / f"musinsa_reviews_{batch_tag}.jsonl"
    return csv_path, jsonl_path


def ensure_csv_header(csv_path: Path) -> list[str]:
    fieldnames = [
        "goods_no",
        "product_url",
        "source_big_category_code",
        "source_big_category_name_ko",
        "source_small_category_code",
        "source_small_category_name_ko_raw",
        "source_small_category_name_ko_norm",
        "page",
        "review_id",
        "content",
        "rating",
        "created_at",
        "option_text",
        "brand_name",
        "goods_name",
        "goods_sex",
        "sale_status",
        "review_type",
        "review_type_name",
        "review_sub_type",
        "like_count",
        "comment_count",
        "comment_reply_count",
        "is_first_review",
        "channel_source",
        "channel_source_name",
        "user_id",
        "encrypted_user_id",
        "review_sex",
        "user_height",
        "user_weight",
        "user_level",
        "survey_size",
        "survey_color",
        "survey_thickness",
        "survey_stretch",
        "repurchase_intent",
        "raw_json",
    ]

    if not csv_path.exists():
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

    return fieldnames


def append_rows_to_csv(csv_path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    if not rows:
        return

    with csv_path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerows(rows)


def append_rows_to_jsonl(jsonl_path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    with jsonl_path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def process_one_small_category(
    session: requests.Session,
    category_info: dict[str, str],
) -> bool:
    """
    청크 실행 1회에서 소분류 하나당 1배치만 처리.
    처리할 상품이 있으면 True, 없으면 False 반환.
    """
    small_dir = get_small_dir(category_info)
    product_urls_file = small_dir / "product_urls.txt"
    processed_file = small_dir / "processed_goods.txt"
    failed_file = small_dir / "failed_goods.txt"
    error_file = small_dir / "errors.log"
    batches_dir = small_dir / "batches"

    small_dir.mkdir(parents=True, exist_ok=True)
    batches_dir.mkdir(exist_ok=True)

    goods_list = load_product_entries(product_urls_file, category_info, error_file)
    processed_goods = load_processed_goods(processed_file)

    if not goods_list:
        print(f"\n[{category_info['small_category_code']}] product_urls.txt가 없거나 비어 있음")
        return False

    batch_goods = select_batch(goods_list, processed_goods)
    if not batch_goods:
        print(f"\n[{category_info['small_category_code']}] 남은 상품 없음")
        return False

    batch_number = get_next_batch_number(batches_dir)
    csv_path, jsonl_path = get_output_paths(batches_dir, batch_number)
    fieldnames = ensure_csv_header(csv_path)

    remaining_count = len(get_remaining_goods(goods_list, processed_goods))

    print(
        f"\n[소분류] {category_info['small_category_code']} - "
        f"{category_info['small_category_name_ko_norm']}"
    )
    print(f"전체 상품 수: {len(goods_list)}")
    print(f"이미 처리한 상품 수: {len(processed_goods)}")
    print(f"남은 상품 수: {remaining_count}")
    print(f"이번 배치 상품 수: {len(batch_goods)}")
    print(f"자동 배치 번호: {batch_number}")

    saved_rows_total = 0
    success_goods = 0
    failed_goods = 0

    for idx, product_info in enumerate(batch_goods, start=1):
        print(f"[{idx}/{len(batch_goods)}] 확인 중: {product_info['product_url']}")

        rows, success = fetch_reviews_for_product(
            session=session,
            product_info=product_info,
            error_file=error_file,
        )

        if not success:
            failed_goods += 1
            append_line(
                failed_file,
                f"{product_info['goods_no']}\t{product_info['product_url']}\trequest_or_paging_failed",
            )
            print("  -> 실패: 다음 실행 때 재시도됨")
            time.sleep(random.uniform(1.0, 2.0))
            continue

        rows = deduplicate_rows(rows)
        append_rows_to_csv(csv_path, rows, fieldnames)
        append_rows_to_jsonl(jsonl_path, rows)
        append_line(processed_file, product_info["goods_no"])

        success_goods += 1
        saved_rows_total += len(rows)

        if rows:
            print(f"  -> 리뷰 {len(rows)}개 저장 완료")
        else:
            print("  -> 리뷰 없음 (상품 처리 완료로 기록)")

        time.sleep(random.uniform(1.0, 2.0))

    print(
        f"[완료] {category_info['small_category_code']} -> "
        f"성공 상품 {success_goods}개 / 실패 상품 {failed_goods}개 / 저장 리뷰 {saved_rows_total}개"
    )
    return True


def main():
    category_rows = load_category_master(CATEGORY_MASTER_CSV)
    chunks = build_chunks(category_rows)
    selected_chunk = choose_chunk(chunks)

    session = create_session()

    worked_count = 0
    for category_info in selected_chunk:
        did_work = process_one_small_category(session, category_info)
        if did_work:
            worked_count += 1

    print("\n===== 청크 실행 종료 =====")
    print(f"이번 실행에서 실제 처리한 소분류 수: {worked_count}/{len(selected_chunk)}")
    print("다음에 같은 청크를 다시 실행하면 남은 상품부터 이어서 진행됩니다.")


if __name__ == "__main__":
    main()