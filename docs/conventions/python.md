# Python Conventions

- 기본 기준은 Google Python Style Guide로 두되, 이 저장소의 기존 모듈 구조와 네이밍이 있으면 그것을 우선한다.
- 새로 작성하거나 수정하는 함수와 메서드에는 가능한 한 type hint를 붙인다.
- public API, 서비스 경계, 데이터 변환 함수의 입력과 출력 타입은 특히 명확하게 적는다.
- 비즈니스 로직, DB 접근, 외부 API 호출, 프레임워크 의존 코드는 분리한다.
- 함수는 한 가지 책임에 집중시키고, I/O와 계산 로직을 가능한 한 분리한다.
- mutable default argument는 사용하지 않는다. 기본값이 필요하면 `None`으로 받고 내부에서 초기화한다.
- 예외 처리는 좁게 잡는다. `except Exception`은 정말 필요한 경우에만 쓰고 의도, 로그, 후속 동작을 남긴다.
- 오류를 삼키지 않는다. 복구 가능한 경우만 fallback을 두고, 아니면 상위로 전달한다.
- 설정값, URL, secret, 환경 의존 값은 코드에 하드코딩하지 않는다.
- 구조화된 데이터는 `dataclass`, `Pydantic model`, `TypedDict` 등으로 명시한다.
- 딕셔너리 남용보다 의미 있는 타입을 우선한다.
- 스크립트와 배치 작업은 가능하면 idempotent하게 작성한다.
- 파일, DB, 외부 시스템을 변경하는 코드는 재실행 시 영향과 롤백 방법을 고려한다.
- 리소스를 여닫는 코드는 context manager를 우선 사용해 종료 경로를 명확히 한다.
- import는 표준 라이브러리, 서드파티, 로컬 순으로 정리하고 한 그룹 안에서는 일관되게 정렬한다.
- 이름은 특별한 이유가 없으면 `lower_with_under`, 클래스는 `CapWords`, 상수는 `CAPS_WITH_UNDER`를 따른다.
- 한 줄에 여러 책임을 압축하지 않는다. comprehension과 축약 문법도 가독성을 해치면 풀어쓴다.
- CLI나 엔트리포인트 코드는 인자 해석과 실제 작업 함수를 분리한다.
- 시간, 파일 경로, 외부 응답처럼 불안정한 입력은 경계에서 정규화한다.
- 로그 메시지는 운영에 도움이 되게 작성한다. 실패 지점, 입력 식별자, 영향 범위를 남긴다.
- 반환 타입이 복잡해지면 tuple보다 명명된 구조를 우선해 호출부 해석 비용을 줄인다.
- 테스트가 있는 프로젝트라면 순수 로직부터 검증하고, I/O 경계는 fixture나 mock으로 분리한다.
- 문서화가 필요한 공개 함수는 입력, 반환값, 부수효과가 드러나게 적는다.

## References

- https://google.github.io/styleguide/
- https://google.github.io/styleguide/pyguide.html
