import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
CATEGORIES_ROOT = BASE_DIR / "categories"
CATEGORY_MASTER_CSV = BASE_DIR / "category_master.csv"


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
                    "small_category_name_ko_norm": str(row.get("small_category_name_ko_norm", "")).strip(),
                }
            )

    rows.sort(key=lambda x: (x["big_category_code"], x["small_category_code"]))
    return rows


def read_nonempty_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def count_csv_rows(csv_path: Path) -> int:
    if not csv_path.exists():
        return 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        row_count = -1  # header 제외
        for _ in reader:
            row_count += 1

    return max(row_count, 0)


def count_jsonl_rows(jsonl_path: Path) -> int:
    if not jsonl_path.exists():
        return 0
    return sum(1 for line in jsonl_path.open("r", encoding="utf-8") if line.strip())


def load_csv_rows(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        return []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def summarize_one_category(category_info: dict[str, str]) -> dict[str, Any]:
    big_code = category_info["big_category_code"]
    small_code = category_info["small_category_code"]

    small_dir = CATEGORIES_ROOT / big_code / small_code
    product_urls_file = small_dir / "product_urls.txt"
    processed_file = small_dir / "processed_goods.txt"
    failed_file = small_dir / "failed_goods.txt"
    error_file = small_dir / "errors.log"
    batches_dir = small_dir / "batches"

    product_urls = read_nonempty_lines(product_urls_file)
    processed_goods = read_nonempty_lines(processed_file)
    failed_goods = read_nonempty_lines(failed_file)
    errors = read_nonempty_lines(error_file)

    batch_csv_files = sorted(batches_dir.glob("musinsa_reviews_batch*.csv")) if batches_dir.exists() else []
    batch_jsonl_files = sorted(batches_dir.glob("musinsa_reviews_batch*.jsonl")) if batches_dir.exists() else []

    total_csv_rows = sum(count_csv_rows(path) for path in batch_csv_files)
    total_jsonl_rows = sum(count_jsonl_rows(path) for path in batch_jsonl_files)

    duplicate_processed = len(processed_goods) - len(set(processed_goods))
    duplicate_failed = len(failed_goods) - len(set(failed_goods))

    processed_goods_set = set()
    failed_goods_set = set()

    for line in processed_goods:
        processed_goods_set.add(line.strip())

    for line in failed_goods:
        # failed_goods.txt는 goods_no\turl\treason 형식일 수 있으므로 첫 컬럼만 추출
        goods_no = line.split("\t")[0].strip()
        if goods_no:
            failed_goods_set.add(goods_no)

    overlap_processed_failed = processed_goods_set & failed_goods_set

    total_products = len(product_urls)
    processed_count = len(processed_goods_set)
    failed_count = len(failed_goods_set)

    processed_ratio = (processed_count / total_products * 100.0) if total_products else 0.0
    failed_ratio = (failed_count / total_products * 100.0) if total_products else 0.0

    reviews_per_processed = (total_csv_rows / processed_count) if processed_count else 0.0

    # 배치별 row 개수
    batch_row_counts = {path.name: count_csv_rows(path) for path in batch_csv_files}

    # 중복 리뷰 점검
    duplicate_review_count = 0
    seen_review_keys = set()

    for csv_path in batch_csv_files:
        rows = load_csv_rows(csv_path)
        for row in rows:
            key = (
                row.get("goods_no", ""),
                row.get("review_id", ""),
                row.get("content", ""),
            )
            if key in seen_review_keys:
                duplicate_review_count += 1
            else:
                seen_review_keys.add(key)

    return {
        "big_category_code": big_code,
        "big_category_name_ko": category_info["big_category_name_ko"],
        "small_category_code": small_code,
        "small_category_name_ko_norm": category_info["small_category_name_ko_norm"],
        "dir_exists": small_dir.exists(),
        "product_urls_exists": product_urls_file.exists(),
        "total_products": total_products,
        "processed_count": processed_count,
        "failed_count": failed_count,
        "processed_ratio": processed_ratio,
        "failed_ratio": failed_ratio,
        "error_count": len(errors),
        "batch_csv_count": len(batch_csv_files),
        "batch_jsonl_count": len(batch_jsonl_files),
        "total_csv_rows": total_csv_rows,
        "total_jsonl_rows": total_jsonl_rows,
        "reviews_per_processed": reviews_per_processed,
        "duplicate_processed": duplicate_processed,
        "duplicate_failed": duplicate_failed,
        "overlap_processed_failed": len(overlap_processed_failed),
        "duplicate_review_count": duplicate_review_count,
        "batch_row_counts": batch_row_counts,
    }


def print_basic_summary(results: list[dict[str, Any]]) -> None:
    print("\n========== 전체 요약 ==========")
    print(f"대상 소분류 수: {len(results)}")
    print(f"디렉터리 존재: {sum(r['dir_exists'] for r in results)}")
    print(f"product_urls.txt 존재: {sum(r['product_urls_exists'] for r in results)}")

    total_products = sum(r["total_products"] for r in results)
    total_processed = sum(r["processed_count"] for r in results)
    total_failed = sum(r["failed_count"] for r in results)
    total_errors = sum(r["error_count"] for r in results)
    total_csv_rows = sum(r["total_csv_rows"] for r in results)
    total_jsonl_rows = sum(r["total_jsonl_rows"] for r in results)
    total_duplicate_reviews = sum(r["duplicate_review_count"] for r in results)

    print(f"전체 상품 URL 수: {total_products}")
    print(f"전체 처리 완료 상품 수: {total_processed}")
    print(f"전체 실패 상품 수: {total_failed}")
    print(f"전체 errors.log 줄 수: {total_errors}")
    print(f"전체 CSV 리뷰 row 수: {total_csv_rows}")
    print(f"전체 JSONL 리뷰 row 수: {total_jsonl_rows}")
    print(f"전체 중복 리뷰 row 수(배치 간 기준): {total_duplicate_reviews}")

    if total_products:
        print(f"전체 처리율: {total_processed / total_products * 100:.2f}%")
        print(f"전체 실패율: {total_failed / total_products * 100:.2f}%")


def print_distribution(results: list[dict[str, Any]]) -> None:
    processed_counts = [r["processed_count"] for r in results]
    review_counts = [r["total_csv_rows"] for r in results]

    print("\n========== 분포 요약 ==========")
    if processed_counts:
        print(
            f"소분류당 처리 완료 상품 수: 평균 {mean(processed_counts):.2f}, "
            f"중앙값 {median(processed_counts):.2f}, "
            f"최소 {min(processed_counts)}, 최대 {max(processed_counts)}"
        )
    if review_counts:
        print(
            f"소분류당 CSV 리뷰 row 수: 평균 {mean(review_counts):.2f}, "
            f"중앙값 {median(review_counts):.2f}, "
            f"최소 {min(review_counts)}, 최대 {max(review_counts)}"
        )


def print_top_categories(results: list[dict[str, Any]], top_n: int = 15) -> None:
    sorted_by_reviews = sorted(results, key=lambda x: x["total_csv_rows"], reverse=True)

    print(f"\n========== 리뷰 row 상위 {top_n}개 소분류 ==========")
    for r in sorted_by_reviews[:top_n]:
        print(
            f"- {r['small_category_code']} ({r['small_category_name_ko_norm']}): "
            f"processed={r['processed_count']}, "
            f"failed={r['failed_count']}, "
            f"reviews={r['total_csv_rows']}, "
            f"errors={r['error_count']}"
        )


def print_suspicious_categories(results: list[dict[str, Any]]) -> None:
    suspicious: list[tuple[dict[str, Any], list[str]]] = []

    for r in results:
        reasons = []

        if not r["product_urls_exists"]:
            reasons.append("product_urls.txt 없음")

        if r["total_products"] > 0 and r["processed_count"] == 0:
            reasons.append("처리 완료 상품 0개")

        if r["processed_ratio"] < 30 and r["total_products"] > 0:
            reasons.append("처리율 30% 미만")

        if r["failed_count"] >= 20:
            reasons.append("실패 상품 20개 이상")

        if r["error_count"] >= 20:
            reasons.append("errors.log 20줄 이상")

        if r["batch_csv_count"] == 0 and r["processed_count"] > 0:
            reasons.append("processed는 있는데 batch CSV 없음")

        if r["total_csv_rows"] == 0 and r["processed_count"] > 0:
            reasons.append("처리된 상품은 있는데 리뷰 row 0개")

        if r["duplicate_processed"] > 0:
            reasons.append(f"processed_goods 중복 {r['duplicate_processed']}개")

        if r["duplicate_failed"] > 0:
            reasons.append(f"failed_goods 중복 {r['duplicate_failed']}개")

        if r["overlap_processed_failed"] > 0:
            reasons.append(f"processed/failed 중복 상품 {r['overlap_processed_failed']}개")

        if r["duplicate_review_count"] > 0:
            reasons.append(f"중복 리뷰 row {r['duplicate_review_count']}개")

        if reasons:
            suspicious.append((r, reasons))

    print("\n========== 의심 소분류 ==========")
    if not suspicious:
        print("특별히 강한 이상 신호는 없습니다.")
        return

    for r, reasons in suspicious:
        print(
            f"- {r['small_category_code']} ({r['small_category_name_ko_norm']}) | "
            f"products={r['total_products']} | processed={r['processed_count']} | "
            f"failed={r['failed_count']} | reviews={r['total_csv_rows']}"
        )
        print(f"  사유: {', '.join(reasons)}")


def print_batch_summary(results: list[dict[str, Any]]) -> None:
    print("\n========== 배치 파일 요약 ==========")
    total_batch_csv = sum(r["batch_csv_count"] for r in results)
    total_batch_jsonl = sum(r["batch_jsonl_count"] for r in results)

    print(f"전체 batch CSV 파일 수: {total_batch_csv}")
    print(f"전체 batch JSONL 파일 수: {total_batch_jsonl}")

    zero_batch_categories = [
        r for r in results if r["batch_csv_count"] == 0 and r["total_products"] > 0
    ]

    if zero_batch_categories:
        print("\nbatch CSV가 없는 소분류:")
        for r in zero_batch_categories[:20]:
            print(f"- {r['small_category_code']} ({r['small_category_name_ko_norm']})")
        if len(zero_batch_categories) > 20:
            print(f"... 외 {len(zero_batch_categories) - 20}개")


def print_status_counter(results: list[dict[str, Any]]) -> None:
    counter = Counter()

    for r in results:
        if r["processed_count"] == 0:
            counter["미시작/처리없음"] += 1
        elif r["processed_count"] < r["total_products"]:
            counter["진행중"] += 1
        else:
            counter["상품 기준 완료"] += 1

    print("\n========== 상태 분류 ==========")
    for key, value in counter.items():
        print(f"- {key}: {value}개")


def main():
    category_rows = load_category_master(CATEGORY_MASTER_CSV)
    results = [summarize_one_category(row) for row in category_rows]

    print_basic_summary(results)
    print_distribution(results)
    print_status_counter(results)
    print_top_categories(results, top_n=15)
    print_batch_summary(results)
    print_suspicious_categories(results)


if __name__ == "__main__":
    main()