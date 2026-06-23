from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .annex_describe import extract_hwp_text
from .config import DATA_DIR
from .corpus import clean_text


OUT_DIR = DATA_DIR / "금융감독_제재검사_내부통제자료"

SOURCES = [
    {
        "title": "대구은행에 대한 금융위원회 제재 의결",
        "url": "https://www.fsc.go.kr/no010101/82133?curPage=49&srchBeginDt=&srchCtgry=&srchEndDt=%2F1000&srchKey=all&srchText=",
        "type": "제재공시/보도참고",
    },
    {
        "title": "금융권 내부통제 제도개선 방안 발표",
        "url": "https://www.fsc.go.kr/no010101/80251",
        "type": "검사제재/내부통제 제도자료",
    },
    {
        "title": "금융권 내부통제 제도개선 TF 중간논의 결과",
        "url": "https://www.fsc.go.kr/no010101/79001",
        "type": "검사제재/내부통제 제도자료",
    },
    {
        "title": "금융회사 내부통제 강화방안",
        "url": "https://www.fsc.go.kr/no010101/71249",
        "type": "검사제재/내부통제 제도자료",
    },
    {
        "title": "금융회사 직원들이 연루된 미공개중요정보 이용행위 적발",
        "url": "https://www.fsc.go.kr/no010101/80544",
        "type": "검사결과/불공정거래",
    },
    {
        "title": "비대면 계좌개설 안심차단 서비스 시행",
        "url": "https://www.fsc.go.kr/no010101/84123",
        "type": "계좌개설 통제 제도자료",
    },
    {
        "title": "경남은행 횡령사고에 대한 검사결과 잠정",
        "url": "https://eiec.kdi.re.kr/policy/callDownload.do?dtime=20230920224347&filenum=1&num=242941",
        "type": "검사결과",
    },
    {
        "title": "제20차 금융위원회 의사록 경남은행 PF대출 내부통제",
        "url": "https://www.fsc.go.kr/comm/getFile?fileNo=2&fileTy=ATTACH&srvcId=BBSTY1&upperNo=83924",
        "type": "제재공시/의사록",
    },
    {
        "title": "제2차 금융위원회 의사록 내부통제 기준 미마련",
        "url": "https://www.fsc.go.kr/comm/getFile?fileNo=1&fileTy=ATTACH&srvcId=BBSTY1&upperNo=81995",
        "type": "제재공시/의사록",
    },
    {
        "title": "내부통제 제도개선 방안 첨부자료",
        "url": "https://www.fsc.go.kr/comm/getFile?fileNo=11&fileTy=ATTACH&srvcId=BBSTY1&upperNo=80251",
        "type": "검사제재/내부통제 제도자료",
    },
]


def safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:90] or "untitled"


def html_text(content: bytes) -> str:
    soup = BeautifulSoup(content, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "form"]):
        tag.decompose()
    main = soup.select_one("#contents, #content, .cont, .view, article") or soup.body or soup
    return clean_text(main.get_text("\n", strip=True))


def pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return clean_text("\n".join(page.extract_text() or "" for page in reader.pages))


def file_extension(response: requests.Response, url: str) -> str:
    ct = (response.headers.get("content-type") or "").lower()
    cd = response.headers.get("content-disposition") or ""
    if ".pdf" in cd.lower() or "pdf" in ct:
        return ".pdf"
    if ".hwp" in cd.lower() or "hwp" in ct:
        return ".hwp"
    path = urlparse(url).path.lower()
    if path.endswith(".pdf"):
        return ".pdf"
    if path.endswith(".hwp"):
        return ".hwp"
    return ".html"


def fetch_source(source: dict) -> dict:
    response = requests.get(source["url"], timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    ext = file_extension(response, source["url"])
    doc_dir = OUT_DIR / "kr" / safe_name(source["title"])
    doc_dir.mkdir(parents=True, exist_ok=True)
    raw_path = doc_dir / f"source{ext}"
    raw_path.write_bytes(response.content)
    if ext == ".pdf":
        text = pdf_text(raw_path)
    elif ext == ".hwp":
        text = extract_hwp_text(raw_path)
    else:
        response.encoding = response.apparent_encoding or "utf-8"
        raw_path.write_text(response.text, encoding="utf-8")
        text = html_text(response.text.encode("utf-8"))

    md_path = doc_dir / "자료.md"
    safe_title = source["title"].replace("'", "''")
    safe_type = source["type"].replace("'", "''")
    front = [
        "---",
        f"제목: '{safe_title}'",
        f"자료유형: '{safe_type}'",
        "출처기관: '금융위원회/금융감독원 관련 공개자료'",
        f"출처: '{source['url']}'",
        f"수집일자: '{date.today().isoformat()}'",
        "---",
        "",
        f"# {source['title']}",
        "",
        f"- 자료유형: {source['type']}",
        f"- 출처: {source['url']}",
        "",
        "## 본문",
        "",
        text or "(본문 추출 실패)",
    ]
    md_path.write_text("\n".join(front).rstrip() + "\n", encoding="utf-8")
    return {
        "title": source["title"],
        "type": source["type"],
        "source_url": source["url"],
        "path": str(md_path.relative_to(OUT_DIR)).replace("\\", "/"),
        "raw_path": str(raw_path.relative_to(OUT_DIR)).replace("\\", "/"),
    }


def write_readme(rows: list[dict]) -> None:
    lines = [
        "# 금융감독 제재·검사·내부통제 자료",
        "",
        "금융회사 내부통제 미비, 제재 의결, 검사결과, 내부통제 제도개선 관련 공개자료를 Markdown으로 정리한 데이터셋입니다.",
        "",
        "## 수집 자료",
        "",
    ]
    lines.extend(f"- {row['title']} ({row['type']})" for row in rows)
    (OUT_DIR / "README.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for source in SOURCES:
        print(source["title"])
        rows.append(fetch_source(source))
    with (OUT_DIR / "index.jsonl").open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_readme(rows)
    print(f"supervision materials done: {len(rows)} -> {OUT_DIR}")


if __name__ == "__main__":
    main()
