from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.legal_graph_rag.agent import AuditFindingReActAgent


SAMPLE_FINDING = """\
금융지주사 감사 결과, 자회사별 내부통제기준 운영 실태 점검이 정기적으로 수행되지 않았고,
준법감시인이 보고한 개선 권고의 이행 여부가 이사회 또는 감사위원회에 체계적으로 보고되지 않았다.
또한 임원별 책무 배분과 관련된 문서가 최신 조직개편 내용을 반영하지 못했다.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", default="샘플금융지주")
    parser.add_argument("--finding", default=SAMPLE_FINDING)
    args = parser.parse_args()

    result = AuditFindingReActAgent().run(args.finding, args.company)
    print(result.answer)
    print("\n--- steps ---")
    for index, step in enumerate(result.steps, start=1):
        print(f"{index}. {step.tool}: {step.thought}")


if __name__ == "__main__":
    main()
