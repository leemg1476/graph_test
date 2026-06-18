# React Conventions

- React 공식 사고방식을 따른다: UI를 작고 재사용 가능한 컴포넌트로 나누고, 데이터 흐름을 먼저 정리한 뒤 구현한다.
- 컴포넌트는 한 가지 주된 책임만 갖게 한다. 화면 조각, 상태 조정, 데이터 로딩을 한 파일에 과하게 섞지 않는다.
- 공통 UI는 조합 가능한 컴포넌트로 추출하되, 너무 이른 추상화는 피한다.
- `props`는 외부 입력, `state`는 컴포넌트가 직접 기억해야 하는 값으로 구분한다.
- `props`는 읽기 전용으로 다루고, 파생 가능한 값은 `state`로 중복 저장하지 않는다.
- client-side state는 최소로 유지한다. 서버 응답, URL, 상위 상태에서 계산 가능한 값은 중복 보관하지 않는다.
- `loading`, `empty`, `error`, `success` 상태를 명시적으로 렌더링한다.
- UI 표시, 상태 관리, API 호출, 도메인 로직은 가능한 한 분리한다.
- 네트워크 호출과 부수효과는 컴포넌트 본문에 흩뿌리지 말고 훅이나 경계 계층으로 모은다.
- 컴포넌트 API는 작고 명확하게 유지한다. 불리언 플래그가 많아지면 분리나 조합을 먼저 검토한다.
- TypeScript를 쓰는 경우 exported component, custom hook, public function에는 명시적 타입을 둔다.
- `any`는 피한다. 필요하면 union, interface, type alias, generics로 의도를 드러낸다.
- 타입 이름과 prop 이름은 사용하는 쪽 맥락보다 컴포넌트 책임을 기준으로 짓는다.
- 파일 안에서만 쓰는 구현 detail은 과도하게 export하지 않는다.
- 폼, 리스트, 비동기 화면은 상태 전이와 사용자 액션을 먼저 적고 컴포넌트를 나눈다.
- semantic HTML을 우선한다. 버튼은 `button`, 네비게이션은 `nav`, 주요 영역은 `main`처럼 의미에 맞는 태그를 쓴다.
- 접근성을 기본값으로 본다. label, alt, heading order, keyboard interaction을 빠뜨리지 않는다.
- 스타일링은 기존 프로젝트 방식이 있으면 그것을 따른다. 새 방식 도입은 명확한 이점이 있을 때만 한다.
- 폴더 구조와 파일 배치는 저장소의 기존 패턴을 우선한다.
- 성능 최적화는 측정 근거가 있을 때 적용한다. 읽기 어려운 memoization을 기본값으로 넣지 않는다.
- 테스트가 있는 프로젝트라면 사용자 동작과 화면 상태를 기준으로 검증한다.

## References

- https://react.dev/
- https://react.dev/learn/thinking-in-react
- https://legacy.reactjs.org/docs/components-and-props.html
- https://google.github.io/styleguide/tsguide.html
- https://google.github.io/styleguide/jsguide.html
