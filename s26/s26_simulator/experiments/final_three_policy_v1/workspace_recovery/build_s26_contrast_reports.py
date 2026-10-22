from pathlib import Path
import hashlib
import json
from html import escape

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'pdf'
QA = ROOT / 'tmp' / 'pdfs' / 's26_contrast'
OUT.mkdir(parents=True, exist_ok=True)
QA.mkdir(parents=True, exist_ok=True)

pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold', 'C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Malgun', normal='Malgun', bold='MalgunBold', italic='Malgun', boldItalic='MalgunBold')

W, H = A4
LEFT = RIGHT = 48
WIDTH = W - LEFT - RIGHT
BOTTOM = 53

STYLES = {
    'body': ParagraphStyle('body', fontName='Malgun', fontSize=10, leading=16.1, wordWrap='CJK', spaceAfter=8.5, textColor=colors.HexColor('#202329')),
    'small': ParagraphStyle('small', fontName='Malgun', fontSize=8.4, leading=12.7, wordWrap='CJK', spaceAfter=7.5, textColor=colors.HexColor('#444B54')),
    'heading': ParagraphStyle('heading', fontName='MalgunBold', fontSize=13.2, leading=20, wordWrap='CJK', spaceBefore=7, spaceAfter=9, textColor=colors.black),
    'table': ParagraphStyle('table', fontName='Malgun', fontSize=8.7, leading=13.1, wordWrap='CJK', textColor=colors.HexColor('#202329')),
    'num': ParagraphStyle('num', fontName='Malgun', fontSize=8.7, leading=13.1, wordWrap='CJK', alignment=TA_CENTER, textColor=colors.HexColor('#202329')),
    'th': ParagraphStyle('th', fontName='MalgunBold', fontSize=8.6, leading=12.5, wordWrap='CJK', alignment=TA_CENTER, textColor=colors.white),
    'title': ParagraphStyle('title', fontName='MalgunBold', fontSize=22.5, leading=31, wordWrap='CJK', spaceAfter=9, textColor=colors.black),
    'subtitle': ParagraphStyle('subtitle', fontName='Malgun', fontSize=11, leading=17, wordWrap='CJK', spaceAfter=12, textColor=colors.black),
}

REFS = {
    1: ('Vepsalainen and Morton 1987', 'Priority Rules for Job Shops with Weighted Tardiness Costs', 'https://doi.org/10.1287/mnsc.33.8.1035'),
    2: ('Mao et al 2016', 'Resource Management with Deep Reinforcement Learning', 'https://people.csail.mit.edu/alizadeh/papers/deeprm-hotnets16.pdf'),
    3: ('Schulman et al 2017', 'Proximal Policy Optimization Algorithms', 'https://arxiv.org/abs/1707.06347'),
    4: ('Goschin et al 2013', 'The Cross Entropy Method Optimizes for Quantiles', 'https://proceedings.mlr.press/v28/goschin13.html'),
}


class Report:
    def __init__(self, path, label, total_pages, biased=False):
        self.path = path
        self.label = label
        self.total_pages = total_pages
        self.biased = biased
        self.c = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
        self.c.setTitle('S26 다중 자원 스케줄링 최종 연구 보고서 ' + label)
        self.c.setAuthor('S26 연구자료 정리')
        self.c.setSubject('기존 동결 결과의 보고서화와 서술 방식 비교')
        self.page = 0
        self.y = H - 48
        self.layout = []

    def start(self, section, first=False):
        if self.page:
            self.c.showPage()
        self.page += 1
        self.c.setFont('Malgun', 8)
        self.c.setFillColor(colors.black)
        self.c.drawString(LEFT, H - 27, 'S26 연구 결과  |  ' + self.label)
        self.c.drawRightString(W - RIGHT, H - 27, '2026년 10월 19일')
        self.c.setFont('Malgun', 7.5)
        self.c.setFillColor(colors.HexColor('#535B65'))
        footer = '비판용 선택적 서술 예시  |  마지막 페이지의 비교 주석과 함께 읽기' if self.biased else '기존 동결 자료 기준  |  모형 결과와 실기기 검증을 구분함'
        self.c.drawString(LEFT, 29, footer)
        self.c.drawRightString(W - RIGHT, 29, f'{self.page} / {self.total_pages}')
        self.y = H - 53
        if not first:
            self.h(section)

    def put(self, flow, after=0):
        before = flow.getSpaceBefore()
        paragraph_after = flow.getSpaceAfter()
        self.y -= before
        width, height = flow.wrap(WIDTH, self.y - BOTTOM)
        if self.y - height < BOTTOM:
            raise RuntimeError(f'Page overflow {self.path.name} page {self.page}: y={self.y}, height={height}')
        flow.drawOn(self.c, LEFT, self.y - height)
        self.y -= height + after + paragraph_after

    def p(self, text, style='body'):
        self.put(Paragraph(text, STYLES[style]))

    def h(self, text):
        self.put(Paragraph(escape(text), STYLES['heading']))

    def title(self, text, subtitle):
        self.put(Paragraph(escape(text), STYLES['title']))
        self.put(Paragraph(escape(subtitle), STYLES['subtitle']))
        self.y -= 5

    def table(self, headings, rows, widths):
        widths = [WIDTH * x / sum(widths) for x in widths]
        data = [[Paragraph(escape(x), STYLES['th']) for x in headings]]
        for row in rows:
            data.append([Paragraph(str(x), STYLES['table'] if i == 0 else STYLES['num']) for i, x in enumerate(row)])
        t = Table(data, colWidths=widths, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#273A50')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F2F5F8')]),
            ('GRID', (0, 0), (-1, -1), 0.55, colors.HexColor('#D9D9D9')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        self.put(t, after=11)

    def refs(self, keys):
        for key in keys:
            author, title, url = REFS[key]
            self.p(f'[{key}] {escape(author)}. {escape(title)}.<br/><link href="{url}" color="#235A85">{url}</link>', 'small')

    def finish(self):
        assert self.page == self.total_pages, (self.page, self.total_pages)
        self.c.save()
        reader = PdfReader(str(self.path))
        assert len(reader.pages) == self.total_pages
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            assert len(text) > 300, (self.path, i, 'missing selectable text')
            if self.biased:
                assert '비판용' in text, (i, 'missing educational label')
        return {'file': str(self.path), 'pages': len(reader.pages), 'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest(), 'selectable_text': True}


def honest():
    r = Report(OUT / 'S26_최종보고서_사실중심.pdf', '사실과 한계를 포함한 버전', 5)
    r.start('연구 요약', first=True)
    r.title('S26 다중 자원 스케줄링\n최종 연구 보고서', '사실과 한계를 포함한 버전')
    r.p('<b>최종 채택안은 롤링 예측과 ATC에 공개 교사학습 초기화 및 PPO를 결합한 정책이다.</b> 기존 85% 명목 부하 평가에서 단일 기본 모델은 단순 EDF보다 모형 전체 에너지를 6.6535%, 평균 AP 예측 온도를 0.6503℃ 낮추고 전체 정시율을 0.3662%p 높였다. 다만 교사학습 직후 모델과의 대조에서는 PPO의 추가 이득을 확인하지 못했다.')
    r.h('원 평가에서의 성과')
    r.table(['방법', '전체 소비\nAPI J', '평균 AP\n℃', '전체 정시율\n%', '미완료'], [
        ['단순 EDF GPU 우선', '833.273', '39.335', '96.704', '0'],
        ['ATC', '832.478', '39.325', '96.582', '0'],
        ['교사학습 직후 고정<br/>PPO 전 대조', '777.781', '38.684', '97.070', '0'],
        ['PPO 3개 seed 평균', '777.827', '38.685', '97.062', '0'],
        ['최종 단일 모델 881087', '777.831', '38.685', '97.070', '0'],
    ], [179, 82, 75, 92, 64])
    r.p('표의 API J는 외부 전력계로 교정하지 않은 API-J이며, AP는 센서 온도의 모형 예측이다. 이 표의 긴급 정시율은 모두 100%다. EDF와 PPO 3개 seed 평균의 완료 응답 P95 회차 평균은 각각 1.632초와 1.554초다. P95는 완료 응답만의 지표이므로 전체 도착 기준 정시율 및 미완료와 함께 읽는다.', 'small')
    r.h('평가 범위와 지표')
    r.p('세션당 1,024요청이며, 두 도착 및 작업 배합 템플릿과 잠재 작업량 2개를 결합한 4세션을 고정 정책별로 평가했다. PPO 평균은 3개 학습 seed의 각 4세션을 평균한 값이다. CPU 서비스 3개 병렬 가정과 지원 경로는 비교 정책에 공통이다. 명목 85%는 입력 생성 조건이며 실기기 CPU 이용률 85%를 측정한 값이 아니다.')
    r.p('관측창은 평균 245.558초이고, PPO 평균의 첫 도착부터 마지막 실제 AVAILABLE까지 작업 경과는 120.294초다. 이는 자원별 실행시간을 합친 값이 아니다. 전체 소비는 관측 시작부터 끝까지 기저와 냉각을 포함한다. 공통 기저는 172.828 API-J이며, 평균 AP는 35초부터 관측 종료까지 계산했다.')

    r.start('방법론과 최종 모델의 구성')
    r.p('우리 정책은 현재 관측한 큐와 자원 상태를 바탕으로 실행할 요청, CPU·GPU·NPU 경로, 대기 여부를 함께 고른다. 최종 행동은 신경망이 선택하며, 납기 충족 여부에 따른 행동 제거 또는 임박 요청 강제 실행은 사용하지 않았다.')
    r.table(['구성', '담당하는 역할'], [
        ['롤링 예측', '현재 보이는 ready 요청 최대 32개의 후속 배정 비용을 명목 모형으로 예측'],
        ['ATC와 공개 후보 규칙', '우선순위와 작업 종류 등을 반영해 요청 후보 최대 8개를 구성'],
        ['신경망 정책', '후보 요청의 지원 경로와 대기를 포함한 최대 27개 행동 중 최종 행동 선택'],
        ['교사학습 초기화', '공개 경로 선호와 요청 순위 규칙의 시연을 행동 복제로 학습'],
        ['PPO 후속 학습', '환경에서 얻은 에너지·열·납기 등의 보상으로 정책 갱신'],
    ], [132, 360])
    r.p('분류 요청은 CPU·GPU·NPU, 탐지 요청은 CPU를 지원한다. 논리 route 슬롯은 각 1개이며 CPU 서비스 작업은 최대 3개까지 병렬이라는 가정을 둔다. 작업은 비선점이고 실제 AVAILABLE까지 소유권을 유지한다. 대기는 20ms, 50ms, 사건 대기를 포함한다. 사건 대기 후에는 진행 중 작업의 AVAILABLE 또는 새 ready 도착에 맞춰 다시 결정한다.')
    r.p('32개 공개 특징을 set encoder와 actor에 넣는다. 실제 미래 도착이나 경로별 잠재 실행시간을 정책 입력으로 제공하지 않는다. 최근 관측 64요청의 배합으로 만든 경로 선호는 특징과 명목 예측에 남아 있다. 따라서 이 정책을 수작업 규칙이 전혀 없는 순수 RL이라고 부를 수 없다.')
    r.h('교사학습과 PPO의 구분')
    r.p('교사학습은 보상 기반 RL이 아니라 규칙 시연을 맞추는 지도학습이다. 공통 교사 모델을 10epoch, 120 optimizer step 학습한 뒤, 동일 초기 가중치에서 3개 PPO seed를 시작했다. seed당 512요청의 2episode와 1회 PPO update, 전체 6episode와 3회 update를 수행했다. 이번 최종안은 과거 초기 가중치와 교사를 제외한 별도 실험과 구분해야 한다.')
    r.p('대표 seed 881087은 원 DEV에서 EVAL 전에 선정했다. 평가에서는 물리적으로 합법인 행동의 logit argmax를 사용한다. 세 seed 평균은 앙상블이나 실제 단일 배포 정책이 아니다. 평가의 군별 가중치는 알려진 명목 배합 p=0.5 또는 0.75를 사용했으므로, 완전히 미지인 온라인 배합에 대한 적응성은 검증하지 않았다.')
    r.p('전력 및 열 계수는 기존 물리·명목 예측 모형에 이미 들어 있다. 열계수 k를 2배·3배·4배로 늘린 가상기기를 만들어 이번 효과를 산출하지 않았다. 임의 온도 상한이나 만들어낸 스로틀링도 넣지 않았다.', 'small')

    r.start('RL 또는 CEM을 검토할 방법론적 근거')
    r.h('우선순위 결정에서 통합 행동 선택으로 확장')
    r.p('ATC 계열은 납기와 지연 비용 및 처리 요구량을 반영하는 우선순위 규칙으로 발전했다.[1] 이 연구에서 추가로 다루는 문제는 어느 작업을 먼저 처리할지에 더해 어느 장치로 보낼지, 빈 자원이 있어도 기다릴지를 정하는 것이다. 현재 선택이 이후 큐와 자원 가용 상태를 바꾸므로 순차 의사결정으로 모델링할 이유가 있다. 다중 자원 작업 배정을 경험 기반 정책으로 학습한 DeepRM은 이 접근의 선행 사례다.[2] 이는 우리 S26 정책의 우위를 입증하는 자료는 아니다.')
    r.p('<b>산업공학 방법이기 때문에 RL이 반드시 필요하다는 논리는 성립하지 않는다.</b> 롤링 예측과 ATC에 고정 경로 규칙이나 예측 비용 최소 선택을 붙여 완결된 휴리스틱을 만들 수도 있다. RL·CEM은 그 선택 함수를 어떻게 정할지에 대한 대안이다. 고정 규칙보다 잘 작동하는지는 별도의 대조 실험으로 판단해야 한다.')
    r.h('정책을 정하는 두 가지 대안')
    r.table(['항목', 'PPO', 'CEM'], [
        ['학습 또는 탐색 대상', '상태별 행동 확률을 내는 정책 가중치', '정책 가중치 등 후보 해의 분포'],
        ['갱신 방법', '환경 경험과 보상을 이용한 정책 기울기 갱신', '후보 평가 후 상위 집단에 맞춰 탐색 분포 갱신'],
        ['검토 이유', '즉시 보상과 이후 결과를 반영하는 순차 정책 학습', '모형 미분 없이 회차 성과로 정책 파라미터 탐색'],
        ['이번 최종안의 위치', '교사 초기화 후 실제 사용한 후속 RL', '최종안에는 없으며 별도 통제 비교의 대안'],
    ], [100, 196, 196])
    r.p('PPO는 환경 상호작용 자료로 정책을 갱신하는 강화학습 알고리즘이다.[3] CEM은 일반적인 확률적 최적화 방법이며, 여기서는 회차 보상으로 정책을 직접 탐색하는 데 사용했다. CEM이라는 이름만으로 PPO와 같은 종류의 RL이라고 단정할 수 없다. 잡음이 있는 평가에서 기본 elite CEM은 기대 보상과 다른 분위수 기준을 선호할 수 있다는 한계도 알려져 있다.[4]')
    r.h('이번 결과에 맞는 연구 목적의 표현')
    r.p('“롤링 예측과 ATC가 제공하는 후보·특징을 유지하면서, 요청·실행 경로·대기의 통합 선택을 신경망 정책으로 표현했다. 공개 규칙의 행동 복제로 초기화한 후, 에너지·열·납기의 누적 비용을 반영하는 PPO 갱신의 추가 개선 가능성을 검토했다. 정책 전체의 EDF 대비 성과는 관측했으나, PPO의 독립적인 추가 이득은 확인하지 못했다.”')

    r.start('기여를 분리하는 대조와 불리한 결과')
    r.h('교사학습 직후 모델과 PPO의 비교')
    r.p('원 85% 평가에서 교사학습 직후 고정 모델은 777.781 API-J, 평균 AP 38.684℃, 정시율 97.070%였다. PPO 3개 seed 평균은 777.827 API-J, 38.685℃, 97.062%였다. PPO 평균은 소비 약 0.006% 증가, 평균 AP 약 0.0006℃ 증가, 정시율 약 0.008%p 감소다. 이 결과는 후속 PPO 학습이 성과를 추가로 높였다는 주장을 지지하지 않는다. 학습량이 seed당 1update였다는 한계가 있지만, 더 학습하면 좋아질 것이라는 결론도 아직 근거가 없다.')
    r.h('교사 없이 처음부터 학습한 별도 비교')
    r.p('아래는 같은 명목 85%이지만 다른 잠재 작업량 8입력에서 실시한 별도 비교다. PPO·CEM은 같은 32파라미터 신경망과 각 432회 학습 예산을 사용했다. 교사·이전 초기 가중치·납기 보호는 없었다. EDF의 기본 경로는 NPU 우선이다. 위 최종 모델 881087은 이 표의 입력에서 평가하지 않았으므로 두 표를 합쳐 순위를 매길 수 없다.')
    r.table(['별도 비교 방법', 'API J', '평균 AP\n℃', '전체 정시율\n%', '미완료\n도착 대비'], [
        ['FIFO', '838.488', '39.4158', '96.948', '0 / 8192'],
        ['EDF', '830.800', '39.3112', '96.643', '0 / 8192'],
        ['순수 롤링과 ATC', '812.514', '39.0914', '84.949', '35 / 8192'],
        ['롤링과 ATC 및 CEM', '827.870', '39.2807', '96.069', '0 / 24576'],
        ['롤링과 ATC 및 PPO', '831.621', '39.3294', '95.959', '0 / 24576'],
    ], [169, 77, 78, 89, 79])
    r.p('PPO·CEM 행은 각 3seed 평가 평균이다. 이 비교에서 CEM은 EDF보다 소비가 0.3527% 낮지만 정시율도 0.5737%p 낮았다. PPO는 EDF보다 소비가 0.0987% 높고 평균 AP가 0.0181℃ 높으며 정시율이 0.6836%p 낮았다. 순수 롤링·ATC는 소비가 낮아도 미완료와 큰 정시율 하락이 있어 동일 완료 작업량의 효율 우위로 해석할 수 없다.')
    r.h('현재 확인한 것과 확인하지 못한 것')
    r.p('확인한 것은 특정 CPU3 모형·입력에서 교사 초기화가 포함된 전체 정책이 원 EDF보다 유리했다는 사실이다. 경로 선호, 사건 대기, 특징 표현, 초기화의 개별 기여는 분리하지 않았다. 전체 성과를 PPO만의 성과로 돌리거나, 최종안에 CEM이 포함되어 있다고 쓰거나, 모든 EDF 기준선에 6.654% 절감을 적용해서는 안 된다.')

    r.start('검증 한계와 최종 판정')
    r.p('<b>모형 내 계산 검산과 실기기 물리 검증은 구분한다.</b> 원자료·행동·PPO 갱신 등의 저장 계산 감사는 통과했지만 전력·열 실측 정확도 gate는 FAIL 상태다. AP 적격 관측 지원 범위는 약 26~46.6℃이며 바깥은 외삽이다. API-J를 교정된 실기기 Joule이나 배터리 절감률로 바꾸어 표현할 수 없다.')
    r.p('CPU3의 추가 코어 소비와 동시 자원 간섭, 휴대전화에서의 롤링 예측·NN·제어 비용은 실측하지 않았다. 기존 CPU 계수를 추가 코어 가동시간에 부과한 저장 궤적 감도에서는 PPO 평균의 EDF 대비 소비 차이가 약 -5.871%였지만, 이는 새 온도·속도 피드백 실행이나 신뢰구간이 아니다. 기존 계수군 감도 역시 물리 정확도 검증을 대신하지 않는다.')
    r.p('도착 패턴은 고정 두 템플릿이며 3개 seed는 학습 난수의 반복이다. 다양한 기기·실사용 분포의 독립 반복을 뜻하지 않는다. 분류=긴급, 탐지=일반이므로 작업종류와 우선순위 효과도 분리되지 않았다. 전체 정시율은 같은 N1024 세션 평균과 pooled 비율이 같지만, 일반·긴급군의 세션 평균과 pooled 비율은 배합에 따라 달라진다. 이번 최종 계열 선택은 여러 결과를 확인한 뒤의 채택 결정이며 새 독립 확인 실험이 아니다.')
    r.p('최종적으로 주장할 수 있는 성과는 <b>납기 강제 보호 없이 교사 초기화가 포함된 하이브리드 정책의 조건부 모형 성과</b>다. PPO를 적용하고 검산한 사실은 명확하지만 PPO의 추가 효용은 미입증이다. CEM은 별도 비교 대안이며 최종 정책의 구성 요소로 보고하지 않는다. 더 넓은 일반화나 실기기 절감은 후속 검증 과제다.')
    r.h('근거 자료')
    r.refs([1, 2, 3, 4])
    r.p('[5] S26 원 결과와 방법론. 아래 게시 자료 및 로컬 FINAL_POLICY_KO.md와 FINAL_POLICY.json. 최종 모델 seed 881087, 체크포인트 SHA256 앞 16자리 4a2c5b1d38da76bd.<br/><link href="https://github.com/mingyujo/D1Check/blob/codex/s26-simulator-handoff-20261016/s26_simulator/publications/route_20261018/README.md" color="#235A85">GitHub 원 결과와 보관 안내</link> · <link href="https://github.com/mingyujo/D1Check/blob/codex/s26-simulator-handoff-20261016/s26_simulator/publications/route_20261018/METHODOLOGY_KO.md" color="#235A85">GitHub 원 방법론</link>', 'small')
    r.p('[6] 로컬 S26_FIVE_POLICY_RESULTS_KO.md 및 S26_MATCHED_PPO_CEM_RESULTS_KO.md. 교사 없는 별도 8입력 비교의 근거다. 원 게시 결과와 입력·정책을 구분했다. 이번 보고서 작성 과정에서 새 시뮬레이션·학습·기기 측정은 수행하지 않았다.', 'small')
    return r.finish()


def selective():
    r = Report(OUT / 'S26_최종보고서_성과강조_비판용예시.pdf', '성과 중심 선택적 서술 예시', 4, biased=True)
    r.start('성과 요약', first=True)
    r.title('S26 다중 자원 스케줄링\n최종 연구 보고서', '성과 중심 선택적 서술 예시')
    r.p('<b>비판용 예시.</b> 본문은 같은 원자료에서 유리한 결과를 중심으로 골라 쓴 버전이다. 수치를 새로 만들지 않았지만 중요한 대조와 한계를 본문에서 생략했다. 반드시 4페이지의 비교 주석과 함께 읽는다.', 'small')
    r.p('우리는 CPU·GPU·NPU 요청 배정을 위해 롤링 예측과 ATC, 교사 초기화 및 PPO를 결합한 학습 기반 하이브리드 정책을 구성했다. 85% 부하 평가에서 이 정책은 EDF보다 에너지와 평균 AP를 낮추면서 전체 정시율을 높였다. 납기 강제 보호 없이 에너지·온도·서비스 지표가 함께 개선되는 결과를 얻었다.')
    r.h('주요 성과')
    r.table(['비교 지표', '단순 EDF', '최종 모델\n881087', '차이'], [
        ['전체 소비 API J', '833.273', '777.831', '6.6535% 감소'],
        ['평균 AP ℃', '39.335', '38.685', '0.6503℃ 감소'],
        ['전체 정시율', '96.704%', '97.070%', '0.3662%p 증가'],
        ['긴급 정시율', '100%', '100%', '유지'],
        ['미완료 요청', '0', '0', '전량 완료'],
    ], [153, 100, 108, 131])
    r.p('세션당 1,024요청을 처리하는 평가에서 전체 소비를 약 55.442 API-J 줄였다. 단순 ATC의 832.478 API-J와 비교해도 최종 정책의 소비가 낮았다. 모든 요청을 완료하고 긴급 정시율 100%를 유지한 점은 작업량 축소나 긴급 서비스 포기로 얻은 절감이 아니라는 점을 보여준다.')
    r.p('기본 모델은 원 DEV 단계에서 고정한 seed 881087이다. 평가용 EVAL에서 최고 seed를 골라 대표로 바꾸지 않았다. 배포 형태가 명확한 단일 모델을 선정하고, 원자료와 체크포인트를 연결해 결과를 추적할 수 있게 했다.')
    r.p('단순 EDF는 실제 ready 큐에서 마감순으로 실행하며 롤링 예측을 사용하지 않았다. 두 정책의 CPU3 조건과 지원 자원은 같게 두고 비교했다.', 'small')

    r.start('산업공학적 예측과 학습 기반 선택의 결합')
    r.p('정책은 산업공학적 우선순위 규칙과 신경망의 행동 선택을 결합한다. ATC가 요청 우선순위 후보를 제공하고, 롤링 예측이 후속 실행의 에너지·열·지연을 추정한다. 신경망은 이 정보를 받아 어떤 요청을 어떤 장치에 보낼지 또는 기다릴지를 한 번에 선택한다.')
    r.table(['구성', '설계 목적'], [
        ['롤링 예측', '현재 선택 이후의 큐와 실행 비용을 판단에 반영'],
        ['ATC 후보 구성', '납기와 처리 요구량을 반영한 우선순위 정보 제공'],
        ['공개 교사학습', '경로 선호와 요청 순위의 유용한 시연으로 정책 초기화'],
        ['PPO', '에너지·열·납기 보상을 활용한 후속 정책 갱신'],
        ['사건 대기', '자원 가용과 새 요청 발생에 맞춰 다음 결정을 수행'],
    ], [145, 347])
    r.h('학습 기반 선택을 검토한 이유')
    r.p('다중 자원 환경에서는 처리 순서만 정해서는 충분하지 않다. CPU·GPU·NPU의 지원 경로와 가용 상태가 다르고, 지금의 배정이 다음 요청의 선택 여지를 바꾼다. 이때 요청·경로·대기의 통합 선택을 정책 함수로 표현하면, 상태에 따라 달라지는 행동을 하나의 구조로 다룰 수 있다. 다중 자원 배정을 경험 기반 정책으로 학습하는 접근은 DeepRM 등 선행 연구에서도 제시되었다.[2]')
    r.p('PPO는 환경 경험과 보상을 통해 정책을 갱신하는 방법이다.[3] 우리는 에너지와 열을 납기와 함께 보상에 반영하고, 목적별 정규화를 적용했다. 물리적으로 불가능한 행동만 제외하며, 납기 가능성 마스크나 임박 요청 강제는 넣지 않았다. 평가에서는 신경망의 최종 출력을 argmax로 선택한다.')
    r.p('CEM은 후보 정책의 회차 성과를 비교해 좋은 파라미터 영역으로 탐색 분포를 옮기는 대안이다.[4] 시뮬레이터의 내부 미분을 요구하지 않는 직접 정책 탐색으로 검토할 수 있다. 이번 최종 기본 모델에는 PPO를 사용했으며, CEM은 별도 비교 방법으로 다뤘다.')
    r.p('산업공학 규칙은 판단에 필요한 구조와 정보를 제공하고, 학습 기반 선택기는 실행 행동을 결정한다. 이러한 구성으로 고정 우선순위 평가를 실행 경로와 대기를 포함하는 통합 의사결정으로 확장했다.')

    r.start('반복 평가 결과와 최종 채택')
    r.h('세 개의 학습 seed를 포함한 결과')
    r.table(['지표', 'EDF', 'PPO 3seed 평균'], [
        ['전체 소비 API J', '833.273', '777.827'],
        ['평균 AP ℃', '39.335', '38.685'],
        ['전체 정시율', '96.704%', '97.062%'],
        ['완료 응답 P95 회차 평균', '1.632초', '1.554초'],
        ['미완료 요청', '0', '0'],
    ], [226, 125, 141])
    r.p('3개 seed 평균에서도 EDF 대비 전체 소비 6.654% 감소와 평균 AP 0.650℃ 감소가 나타났다. 전체 정시율은 97.062%였고 긴급 정시율 100%를 유지했다. 원 85% 입력과 seed를 짝지은 12쌍 모두에서 EDF 대비 전체·긴급·일반 정시율과 완료를 악화시키지 않았다. 이 평균은 3개 개별 정책의 평가 평균이며 앙상블은 아니다.')
    r.p('관측창 평균 245.558초에 기저와 냉각을 포함한 전체 소비를 비교했다. 공통 기저를 제외한 증분 소비 기준에서는 8.395% 감소했다. 주 성과는 기저를 포함한 6.654%로 제시하며 두 분모를 구분한다.')
    r.h('최종 채택')
    r.p('최종 연구 정책으로 롤링 예측·ATC·공개 교사학습 초기화·PPO의 조합을 채택했다. 이 정책은 단순 EDF와 비교해 전체 소비, 평균 AP, 정시율의 동시 개선을 보였고, 납기 강제 보호 없이 요청 처리를 완료했다. CPU·GPU·NPU 경로 선택과 사건 대기를 함께 다루는 하이브리드 스케줄링의 적용 가능성을 보여주는 결과다.')
    r.h('본문의 참고 자료')
    r.refs([2, 3, 4])
    r.p('성과 수치는 기존 route_group_learning_v1의 원 85% 평가 및 로컬 FINAL_POLICY_KO.md를 따른다. 원 공개 자료는 <link href="https://github.com/mingyujo/D1Check/blob/codex/s26-simulator-handoff-20261016/s26_simulator/publications/route_20261018/README.md" color="#235A85">GitHub S26 결과와 방법론</link>에 연결되어 있다. 앞의 세 페이지는 성과 중심의 선택적 서술이며 아래 비교 주석이 해석 범위를 정한다.', 'small')

    r.start('비판용 예시의 비교 주석')
    r.p('<b>이 페이지는 앞선 성과 중심 서술이 무엇을 빠뜨렸는지 명시한다.</b> 앞의 표에 사용한 수치는 사실 중심 버전과 같은 값이다. 그러나 다음 정보가 빠지면 독자는 연구가 입증한 범위를 실제보다 넓게 받아들일 수 있다.')
    r.h('교사학습 대조를 생략한 효과')
    r.p('교사학습 직후 고정 모델의 777.781 API-J, 38.684℃, 정시율 97.070%를 본문 결과표에서 뺐다. 이 모델은 PPO 3seed 평균보다 소비가 약 0.006% 낮고 정시율이 약 0.008%p 높았다. 따라서 EDF 대비 개선을 “강화학습이 만들어낸 추가 절감”으로 읽으면 잘못된 원인 귀속이다. 최종 단일 PPO 모델도 이 대조보다 더 나은 결과를 보이지 않았다.')
    r.h('모형의 성과를 실기기로 받아들이게 되는 효과')
    r.p('본문은 API-J와 AP를 제시하면서 전력·열 실측 정확도 gate FAIL, CPU3 추가 전력·열·간섭 미측정, 기기에서의 제어 비용 미측정을 생략했다. 이를 읽고 S26 실기기의 배터리 절감과 온도 개선이 검증됐다고 생각하면 증거 범위를 넘는다. 계산 검산 통과와 물리 정확도 검증은 다르다.')
    r.h('불리한 별도 비교를 생략한 효과')
    r.p('교사 없는 같은 32파라미터 정책의 별도 비교에서는 CEM이 EDF보다 소비를 0.3527% 줄였지만 정시율도 0.5737%p 낮췄고, PPO는 소비·평균 AP·정시율 모두 EDF보다 불리했다. 이는 현재 최종 모델의 직접 대조는 아니지만 “RL이나 CEM을 붙이면 일반적으로 좋아진다”는 주장을 제한한다. 원 평가와 입력·신경망·기준 경로가 다르므로 수치를 섞어서 순위를 만들 수도 없다.')
    r.h('방법론의 가능성과 필수성을 혼동하는 효과')
    r.p('ATC가 우선순위 규칙이라는 사실은 RL을 반드시 붙여야 한다는 결론을 주지 않는다.[1] 고정 경로 규칙이나 예측 비용 최소 선택도 대안이다. 선행 논문은 RL·CEM을 검토할 이유를 주지만 우리 정책에서 그 방법이 필요하거나 더 좋다는 증거를 대신하지 않는다. 교사학습은 지도학습이고 CEM은 최종 채택 모델에 없다.')
    r.p('3seed와 고정 두 도착 템플릿의 반복은 다양한 기기·분포의 일반화 증거가 아니다. 정시율 96.704%에서 97.070%의 차이는 0.366%p이며, 전체 정시율이 큰 폭으로 향상되었다는 표현은 근거가 약하다. 8.395%는 기저 제외 증분 소비이고 6.654%는 전체 소비다. 이 분모와 단일 모델·3seed 평균을 바꾸어 쓰면 같은 숫자로도 성과가 과장된다.', 'small')
    r.p('[1] <link href="https://doi.org/10.1287/mnsc.33.8.1035" color="#235A85">Vepsalainen and Morton 1987 ATC 계열 우선순위 규칙</link>. 모든 주석의 수치·한계·대조는 사실 중심 버전 및 그 근거 문서에서 확인할 수 있다. 이 문서는 선택적 서술의 영향을 비교하는 예시이며 실제 성능 입증 자료로 단독 사용하지 않는다.', 'small')
    return r.finish()


outputs = [honest(), selective()]
manifest = {
    'date': '2026-10-19',
    'outputs': outputs,
    'source_files': [],
    'new_simulation_runs': 0,
    'new_training_runs': 0,
    'new_measurements': 0,
    'intent': 'Two S26 report presentations for comparison; not a separate report about LLM risks',
}
for rel in [
    's26_simulator/FINAL_POLICY_KO.md',
    's26_simulator/FINAL_POLICY.json',
    's26_simulator/S26_ROUTE_GROUP_RESULTS_KO.md',
    's26_simulator/S26_FIVE_POLICY_RESULTS_KO.md',
    's26_simulator/S26_MATCHED_PPO_CEM_RESULTS_KO.md',
    's26_simulator/publications/route_20261018/METHODOLOGY_KO.md',
]:
    path = ROOT / 'S26-D1Check' / rel
    manifest['source_files'].append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
(QA / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(outputs, ensure_ascii=False, indent=2))
