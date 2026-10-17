# V1 사전 잠재 벡터 비교 중단

게시 d1fcb9835b14b4d48cd0d215191cf3c5fef028c6, OP SHA8962410e557884e04d864e36e18fe997842fbe657a542a2c1bc34bbe0cb8631b. 원 소스·START/FAILURE는 보존한다. 실제 환경 START=0, MILP=0이며 동결 은행 복원은 1회 소비했다. `_whole_vector`는 tuple을 반환하지만 JSON 저장은 list로 읽으므로 같은 수치 벡터도 직접 동등 비교에서 False였다. V2에서 비교 양쪽을 list로 정규화한다. 물리·표본·난수·수학 하한·입력·예산 상한은 변경하지 않는다.

새 별도 V2 namespace를 사전 게시하며 미사용 환경288을 전부 이전한다. 전역 예약 추가0, 합계125766 유지, 원coupled 잔38/RR잔1 불변이다. V2의 동결 은행 복원 1회는 별도로 명시한다. 원 완료 operation 재실행 및 원 실패 덮어쓰기0이다.
