import csv
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CATEGORIES_ROOT = BASE_DIR / "categories"
FINAL_DIR = BASE_DIR / "final"


def get_big_category_dirs() -> list[Path]:
    dirs = [p for p in CATEGORIES_ROOT.iterdir() if p.is_dir() and p.name.isdigit()]
    dirs.sort(key=lambda p: p.name)
    return dirs


def collect_merged_csv_files() -> list[Path]:
    csv_files = []

    for big_dir in get_big_category_dirs():
        merged_dir = big_dir / "merged"
        if not merged_dir.exists():
            continue

        files = sorted(merged_dir.glob("musinsa_reviews_*_all.csv"))
        csv_files.extend(files)

    return csv_files


def read_csv_rows(csv_path: Path) -> list[dict]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def deduplicate_rows(rows: list[dict]) -> list[dict]:
    seen = set()
    deduped = []

    for row in rows:
        key = (
            row.get("goods_no", ""),
            row.get("review_id", ""),
            row.get("content", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


def save_csv(rows: list[dict], output_path: Path) -> None:
    if not rows:
        print("저장할 CSV 행이 없습니다.")
        return

    output_path.parent.mkdir(exist_ok=True)

    fieldnames = list(rows[0].keys())

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_jsonl(rows: list[dict], output_path: Path) -> None:
    if not rows:
        print("저장할 JSONL 행이 없습니다.")
        return

    output_path.parent.mkdir(exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    csv_files = collect_merged_csv_files()
    if not csv_files:
        print("합칠 대분류 merged CSV 파일이 없습니다.")
        return

    print(f"발견한 대분류 merged CSV 파일 수: {len(csv_files)}")

    all_rows = []
    for csv_file in csv_files:
        rows = read_csv_rows(csv_file)
        all_rows.extend(rows)
        print(f"  - {csv_file} -> {len(rows)}행")

    print(f"\n합치기 전 총 행 수: {len(all_rows)}")
    all_rows = deduplicate_rows(all_rows)
    print(f"중복 제거 후 총 행 수: {len(all_rows)}")

    output_csv = FINAL_DIR / "musinsa_reviews_all.csv"
    output_jsonl = FINAL_DIR / "musinsa_reviews_all.jsonl"

    save_csv(all_rows, output_csv)
    save_jsonl(all_rows, output_jsonl)

    print("\n전체 합치기 완료")
    print(f"CSV 저장: {output_csv}")
    print(f"JSONL 저장: {output_jsonl}")


if __name__ == "__main__":
    main()