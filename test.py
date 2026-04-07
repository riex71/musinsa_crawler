import requests

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


def main():
    goods_no = input("확인할 goodsNo를 입력하세요: ").strip()
    if not goods_no:
        print("goodsNo가 비어 있습니다.")
        return

    params = {
        "goodsNo": goods_no,
        "page": 0,
        "pageSize": 20,
    }

    response = requests.get(API_URL, params=params, headers=HEADERS, timeout=20)
    response.raise_for_status()
    data = response.json()

    items = data.get("data", {}).get("list", [])
    if not items:
        print("리뷰가 없거나 응답 형식이 예상과 다릅니다.")
        return

    print(f"\n[goodsNo={goods_no}] 첫 페이지 리뷰 {len(items)}개\n")

    for idx, item in enumerate(items, start=1):
        content = (
            item.get("content")
            or item.get("reviewContent")
            or item.get("goodsOpinionContents")
            or ""
        )
        score = item.get("score") or item.get("grade") or item.get("point") or ""
        created_at = (
            item.get("createDate")
            or item.get("regDate")
            or item.get("writeDate")
            or ""
        )
        like_count = item.get("likeCount", 0) or 0
        review_id = item.get("no") or item.get("reviewNo") or item.get("goodsOpinionNo") or ""

        preview = str(content).replace("\n", " ").strip()
        if len(preview) > 80:
            preview = preview[:80] + "..."

        print(
            f"{idx:02d}. "
            f"review_id={review_id} | "
            f"score={score} | "
            f"date={created_at} | "
            f"like={like_count} | "
            f"text={preview}"
        )


if __name__ == "__main__":
    main()