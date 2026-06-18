# LangGraph Conventions

- LangGraph는 stateful agent orchestration을 위한 저수준 프레임워크로 보고, 상태와 실행 흐름을 먼저 설계한 뒤 노드를 구현한다.
- agent state는 명시적이고 typed schema로 정의한다. 암묵적인 딕셔너리 키 추가에 의존하지 않는다.
- state 필드는 최소화하고, 각 필드의 생성 주체와 소비 노드를 분명히 한다.
- node는 하나의 명확한 책임만 갖게 한다. prompting, parsing, persistence, routing을 한 node에 몰아넣지 않는다.
- graph routing 조건은 읽기 쉽고 테스트 가능하게 작성한다.
- 분기 로직은 "어떤 state가 어떤 edge를 타는지"가 코드만 보고 드러나야 한다.
- routing 함수는 가능하면 순수 함수로 유지해 단위 테스트가 가능하게 만든다.
- prompt, schema, tool, node, graph assembly 코드는 분리한다.
- tool input, LLM output, tool result는 모두 검증한다. 모델이나 외부 도구 출력을 신뢰하지 않는다.
- 구조화된 출력이 필요하면 parser나 schema validation을 통해 실패를 조기에 드러낸다.
- tool node는 외부 부수효과와 재시도 정책을 명확히 가진다.
- 결정적 변환 로직은 가능한 한 일반 Python 함수로 두고, 모델 호출 node와 분리한다.
- checkpoint, memory, persistence를 사용할 때는 저장 범위와 side effect를 분명히 한다.
- 어떤 상태를 영속화하는지, 어떤 상태는 런타임 전용인지 구분한다.
- streaming 이벤트 처리와 최종 응답 조립 로직은 분리한다.
- 사용자에게 보이는 중간 이벤트와 최종 답변은 서로 다른 책임으로 다룬다.
- retry, timeout, fallback, error path를 명시적으로 설계한다.
- 실패 시 어떤 state를 남기고 어디서 복구하는지 코드와 로그에 드러나야 한다.
- state 업데이트는 덮어쓰기보다 의도적인 병합과 누적을 우선해 추적 가능성을 유지한다.
- persistent data mutation은 명확한 사용자 의도나 workflow intent가 있을 때만 수행한다.
- 사람 승인, 쓰기 작업, 외부 시스템 변경은 가능한 한 분리된 node나 guard로 감싼다.
- 최종 답변은 retrieved evidence, tool result, state transition을 통해 추적 가능해야 한다.
- 디버깅 시 어떤 node가 어떤 입력으로 실행됐는지 추적 가능한 로그와 trace를 남긴다.
- 기존 LangGraph 코드가 있다면 `StateGraph` 구성 방식, node naming, tool binding, checkpointer 패턴을 우선한다.

## References

- https://docs.langchain.com/oss/python/langgraph/overview
- https://github.com/langchain-ai/langgraph
