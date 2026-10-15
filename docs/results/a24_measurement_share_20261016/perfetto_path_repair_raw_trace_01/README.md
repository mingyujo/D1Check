# 수정 경로에서 회수한 Perfetto 원본

[원본 ZIP](TRACE2_ON_original_trace.zip) · [ZIP·원파일 SHA와 검사 범위](RAW_TRACE_SHA256.json)

새OFF/ON대조2회는각분류GPU32건을정상처리했고출력오류0,AP관측창은둘다적격이었다. 이ZIP은그중ON의 **원본trace 8,979,426바이트**와변경없는계측profile·원래회수영수증이다. 압축해제한세원파일이로컬원본과바이트단위로같음을검산했다. 모델·입력영상·APK는포함하지않는다.

- 원본trace SHA-256: `7fab42d3051518df1e10af2a43ec74d54181a6c3e5d9d19c7364fe1c3a04cf81`
- ZIP SHA-256: `007bcba454d9d9e34b7bee9a4450652b79a0d9a7db247e2cca416f79d1931ed9`
- 등록된고유하드웨어serial·연결주소·논리device ID와기존개인경로패턴은검색되지않았다. **일반적인OS빌드fingerprint는포함**하며프로필상시스템스케줄러의프로세스/스레드이름이포함될수있다. 이검색을모든개인정보부재에대한일반적증명으로과장하지않는다. 원본을수정해서같은바이트라고표시하지않았다.
- 회수시영수증은 `RAW_TRACE_ONLY_SOURCES_AND_LOSS_UNVERIFIED`를유지한다. 210초자체만료뒤attach/stop에세션이없었다는오류도원래대로남겼다. **자료원·유실의PC분석은별도검증**이며, 이원본회수만으로하드웨어카운터·물리에너지J·표면온도검증이완료되는것은아니다.

일반비교군ZIP은바이너리를기본제외하고SHA/이유를기록한다. 사용자의원자료공유요청에따라이자체계측trace는분리해원바이트로제공한다. [OFF/ON의다른원자료·상태](../automatic_checkpoints/TRACE2_TRACE_REPAIR_I_C32/README.md)와[설정경로수정·고정계획](../../../team/a24-measurement-revision02-20261015/trace_path_repair2_20261016/README.md)을함께본다.
