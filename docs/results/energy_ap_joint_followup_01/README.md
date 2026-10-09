# 열·에너지 정확도 개선의 실제 동시 판독

[보고서](../../ENERGY_AP_JOINT_FOLLOWUP_PC_20261010.md)·[화면](index.html)·[실행 전 역할/구조 등록](registration.json).

에너지를빠뜨린AP-only후속을수정해기존개발4로에너지후보1개를추정하고전체35세션을평가했다. 새600초는개선했으나긴유휴가악화했다. 원AP후보/동결모형/기본/RL/strict/experiment_ready=false 유지,추가실측/ADB0.

`run_v1`의candidate/fold/fit_receipt는한번추정한자료이며evaluate는재추정하지않는다. AP는기존동결값과기존오차를재사용했고에너지계수변경을AP식에역으로넣지않았다. 실제일정조건부A,종단간B와구분한다.

공유된작은입력GZip4묶음과원식/후보JSON으로PC수치재현가능하다. 원자료를기기에서재수집하지않는다. 설치키·APK·모델weights·원센서대용량파일·기기식별정보를포함하지않는다.
