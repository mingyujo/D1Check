# V3 확인의 온도 조회 timeout 수집기 보완

2026-10-10 22:39 KST. 첫 CPU 확인은 본작업 전에 무선 ADB thermalservice 조회의2초timeout으로중단됐다. client stdout0/실제elapsed2.015초, 원stack/receipt/반환prefix보존, host앱종료completed/status0이다. runtime4확인/warmup확인4·상한8/본작업확인0·상한96을보존하며 결측완료를가정하지않는다. 후보56a663bc…/APK356c668f…는불변이다.

새ID/UUID4회의수집기는 온도 관련세명령의 응답timeout만3초로한다. 기존전체before..after≤4초/uncertainty≤2초·열status0·샘플간격/완전창/센서검증을그대로적용한다. 제한을넘은조회는버리고진행하거나재시도하지않고중단한다. 공유ADBdaemon 시작/재연결/전송재시도는하지않는다.

원4확인·재적합0을유지하며 본작업전실패1을더한 물리시도상한5/runtime20/명시추론upper520(새416＋실패upper104)/staging5·35파일로명시개정한다. 이미설치된동일APK만점검해추가설치0이며누적설치1/hostAPKpull2다. 실패119 ADB슬롯＋새상한5785＝원5904, 새정상5704를유지해남은81을종료예약으로둔다.

새예약4530초와 최초확인claim＋5130초의종료monotonic 중작은값을쓴다. 원clock을다시시작하지않는다. 실패/지연으로원clock예약이부족하면자동연장하지않는다. 같은모형·기한·요청·원시계약·20미만허용6%조건·CPU/PAR/PAR/CPU를그대로새미소비namespace에서수행한다. 본작업전수집실패에따른보완이며확인성능이좋지않아자료를바꾼것이아니다.
