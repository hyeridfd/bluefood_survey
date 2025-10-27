import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import gspread
import os
import traceback
from google.oauth2.service_account import Credentials
import matplotlib.pyplot as plt
import seaborn as snsㄹ
import matplotlib as mpl
import matplotlib.font_manager as fm
from matplotlib import rcParams
import urllib.request
import json

# ===================== 기본 설정 / 스타일 =====================

LIGHT_FORCE_CSS = """
<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], [data-testid="stApp"] {
    background-color: #ffffff !important;
    color: #000000 !important;
}
.block-container {
    color: #000000 !important;
}
hr {
    border-color: #cccccc !important;
}

/* 3열 그리드 강제 */
[data-testid="stHorizontalBlock"] {
    display: grid !important;
    grid-template-columns: repeat(3, 1fr) !important;
    gap: 8px !important;
    width: 100% !important;
}
[data-testid="stHorizontalBlock"] > div {
    min-width: 0 !important;
}
[data-testid="stColumn"] {
    width: 100% !important;
    flex: 1 1 auto !important;
}

/* 모바일에서도 동일하게 3열 유지 */
@media (max-width: 768px) {
    [data-testid="stHorizontalBlock"] {
        grid-template-columns: repeat(3, 1fr) !important;
    }
}

/* 선택 버튼 스타일 */
button[kind="secondary"], button[kind="primary"] {
    width: 100% !important;
    padding: 10px 8px !important;
    white-space: normal !important;
    word-break: break-word !important;
    font-size: 14px !important;
    line-height: 1.3 !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}
</style>
"""

JS_PATCH = """
<script>
window.addEventListener('load', function() {
    function fixLayout() {
        const cols = document.querySelectorAll('[data-testid="stColumn"]');
        cols.forEach(col => {
            col.style.flex = '1 1 calc(33.33% - 6px)';
            col.style.minWidth = 'calc(33.33% - 6px)';
        });

        const btns = document.querySelectorAll('button');
        btns.forEach(btn => {
            btn.style.width = '100%';
            btn.style.whiteSpace = 'normal';
            btn.style.wordBreak = 'break-word';
        });
    }
    setTimeout(fixLayout, 500);
    setInterval(fixLayout, 1500);
});
</script>
"""

st.set_page_config(
    page_title="블루푸드 선호도 조사",
    page_icon="🐟",
    layout="wide"
)
st.markdown(LIGHT_FORCE_CSS, unsafe_allow_html=True)
st.markdown(JS_PATCH, unsafe_allow_html=True)

# ===================== 폰트(한글 깨짐 방지) =====================

FONT_PATH = "/tmp/NanumGothic.ttf"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"

if not os.path.exists(FONT_PATH):
    try:
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
    except Exception as e:
        print(f"⚠️ 폰트 다운로드 실패: {e}")

try:
    fontprop = fm.FontProperties(fname=FONT_PATH)
    rcParams['font.family'] = fontprop.get_name()
    mpl.rcParams['font.family'] = fontprop.get_name()
    mpl.rcParams['axes.unicode_minus'] = False
except Exception as e:
    print(f"⚠️ 폰트 로드 실패, 기본 폰트 사용: {e}")
    fontprop = None

# ===================== 시간/환경 =====================

KST = timezone(timedelta(hours=9))
ADMIN_PASSWORD = "bluefood2025"

def get_korean_time():
    return datetime.now(KST)

def format_korean_time():
    return get_korean_time().strftime('%Y-%m-%d %H:%M:%S')


# ===================== Google Sheets 연결 & 저장 =====================

def get_google_sheet_cached():
    """Google Sheets 연결 (안전 버전)"""
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("❌ gcp_service_account 누락")
            return None
        
        if "google_sheets" not in st.secrets:
            st.error("❌ google_sheets 설정 누락")
            return None
        
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            pk = creds_dict["private_key"]
            if "\\n" in pk:
                creds_dict["private_key"] = pk.replace("\\n", "\n")

        cfg = st.secrets["google_sheets"]
        sheet_name = cfg.get("google_sheet_name")
        sheet_id = cfg.get("google_sheet_id")

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets"
        ]

        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)

        sheet = None
        if sheet_id:
            try:
                workbook = client.open_by_key(sheet_id)
                sheet = workbook.sheet1
            except Exception:
                pass
        if sheet is None and sheet_name:
            try:
                workbook = client.open(sheet_name)
                sheet = workbook.sheet1
            except Exception as e:
                st.error(f"❌ 시트 열기 실패: {e}")
                return None

        if sheet is None:
            st.error("❌ 시트를 찾을 수 없습니다.")
            return None

        # 헤더 없으면 생성
        first_row = sheet.row_values(1)
        if not first_row or all(cell == '' for cell in first_row):
            headers = ['이름', '식별번호', '설문일시', '선택한_수산물', '선택한_메뉴']
            sheet.append_row(headers)

        return sheet
    except Exception as e:
        st.error(f"❌ Google Sheets 연결 오류: {e}")
        st.code(traceback.format_exc())
        return None


def save_to_google_sheets(name, id_number, selected_ingredients, selected_menus):
    """Google Sheets 저장 (에러 나도 설문은 진행 가능)"""
    try:
        sheet = get_google_sheet_cached()
        if sheet is None:
            return False

        menus_text = json.dumps(selected_menus, ensure_ascii=False)
        ingredients_text = json.dumps(selected_ingredients, ensure_ascii=False)
        now_str = format_korean_time()

        new_row = [name, id_number, now_str, ingredients_text, menus_text]
        sheet.append_row(new_row)

        st.session_state.google_sheets_success = True
        return True
    except Exception as e:
        print(f"⚠️ Google Sheets 저장 오류: {e}")
        st.session_state.google_sheets_success = False
        return False


def save_to_excel(name, id_number, selected_ingredients, selected_menus):
    """로컬 백업 엑셀 저장"""
    try:
        filename = "bluefood_survey.xlsx"

        if os.path.exists(filename):
            df = pd.read_excel(filename)
        else:
            df = pd.DataFrame(columns=['이름', '식별번호', '설문일시', '선택한_수산물', '선택한_메뉴'])

        menus_text = json.dumps(selected_menus, ensure_ascii=False)
        ingredients_text = json.dumps(selected_ingredients, ensure_ascii=False)
        now_str = format_korean_time()

        new_row = {
            '이름': name,
            '식별번호': id_number,
            '설문일시': now_str,
            '선택한_수산물': ingredients_text,
            '선택한_메뉴': menus_text
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        df.to_excel(filename, index=False)
        
        return filename, df
    except Exception as e:
        print(f"❌ Excel 저장 오류: {e}")
        return None, None


# ===================== Session State 초기화 =====================

if 'step' not in st.session_state:
    st.session_state.step = 'info'        # info -> category -> complete  👈 핵심
if 'name' not in st.session_state:
    st.session_state.name = ""
if 'id_number' not in st.session_state:
    st.session_state.id_number = ""
if 'selected_ingredients' not in st.session_state:
    st.session_state.selected_ingredients = []  # 전체 누적
if 'selected_menus' not in st.session_state:
    st.session_state.selected_menus = {}        # {재료: [메뉴,...]}
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'show_admin_login' not in st.session_state:
    st.session_state.show_admin_login = False
if 'google_sheets_success' not in st.session_state:
    st.session_state.google_sheets_success = False
if 'already_saved' not in st.session_state:
    st.session_state.already_saved = False

# 👈 핵심: 지금 몇 번째 카테고리를 진행중인지
if 'category_index' not in st.session_state:
    st.session_state.category_index = 0


# ===================== 설문 데이터 (수산물/메뉴) =====================

MENU_DATA = {
    '맛살': {'밥/죽': ['게맛살볶음밥'], '무침': ['게맛살콩나물무침'], '볶음': ['맛살볶음'], '부침': ['맛살전']},
    '어란': {
        '밥/죽': ['날치알밥'],
        '면류': ['명란파스타'],
        '국/탕': ['알탕'],
        '찜': ['날치알달걀찜'],
        '무침': ['명란젓갈'],
        '볶음': ['날치알스크램블에그'],
        '부침': ['날치알계란말이'],
        '구이': ['명란구이']
    },
    '어묵': {
        '밥/죽': ['어묵볶음밥'],
        '면류': ['어묵우동'],
        '국/탕': ['어묵탕'],
        '조림': ['어묵조림'],
        '찜': ['콩나물어묵찜', '어묵찜'],
        '볶음': ['매콤어묵볶음', '간장어묵볶음'],
        '부침': ['어묵전'],
        '튀김': ['어묵고로케']
    },
    '쥐포': {
        '조림': ['쥐포조림'],
        '무침': ['쥐포무침'],
        '볶음': ['쥐포볶음'],
        '부침': ['쥐포전'],
        '튀김': ['쥐포튀김'],
        '구이': ['쥐포구이']
    },
    '김': {'밥/죽': ['김밥'], '무침': ['김무침'], '튀김': ['김부각'], '구이': ['김자반']},
    '다시마': {'무침': ['다시마채무침'], '볶음': ['다시마채볶음'], '튀김': ['다시마튀각']},
    '매생이': {'면류': ['매생이칼국수'], '국/탕': ['매생이굴국'], '부침': ['매생이전']},
    '미역': {'밥/죽': ['미역국밥'], '국/탕': ['미역국'], '무침': ['미역초무침'], '볶음': ['미역줄기볶음']},
    '파래': {'무침': ['파래무침'], '볶음': ['파래볶음'], '부침': ['물파래전']},
    '톳': {'밥/죽': ['톳밥'], '무침': ['톳무침']},
    '꼴뚜기': {'조림': ['꼴뚜기조림'], '찜': ['꼴뚜기찜'], '무침': ['꼴뚜기젓무침'], '볶음': ['꼴뚜기볶음']},
    '낙지': {
        '밥/죽': ['낙지비빔밥'],
        '면류': ['낙지수제비'],
        '국/탕': ['낙지연포탕'],
        '찜': ['낙지찜'],
        '무침': ['낙지초무침'],
        '볶음': ['낙지볶음'],
        '구이': ['낙지호롱구이'],
        '기타(생식)': ['낙지탕탕이']
    },
    '문어': {
        '밥/죽': ['문어볶음밥'],
        '면류': ['문어라면'],
        '국/탕': ['문어탕'],
        '조림': ['문어조림'],
        '찜': ['문어콩나물찜'],
        '무침': ['문어초무침'],
        '볶음': ['문어볶음'],
        '부침': ['문어전'],
        '튀김': ['문어튀김'],
        '기타(생식)': ['문어회']
    },
    '오징어': {
        '밥/죽': ['오징어덮밥'],
        '국/탕': ['오징어무국'],
        '조림': ['오징어조림'],
        '찜': ['오징어콩나물찜', '오징어숙회'],
        '무침': ['오징어초무침'],
        '볶음': ['오징어볶음'],
        '부침': ['오징어해물전'],
        '튀김': ['오징어튀김'],
        '구이': ['오징어버터구이'],
        '기타(생식)': ['오징어회']
    },
    '주꾸미': {
        '밥/죽': ['주꾸미볶음덮밥'],
        '면류': ['주꾸미감자수제비', '주꾸미짬뽕'],
        '국/탕': ['주꾸미연포탕'],
        '찜': ['주꾸미숙회', '주꾸미찜'],
        '무침': ['주꾸미무침'],
        '볶음': ['주꾸미볶음']
    },
    '가재': {'찜': ['가재찜'], '구이': ['가재구이']},
    '게': {
        '밥/죽': ['게살볶음밥'],
        '면류': ['게살파스타', '꽃게라면'],
        '국/탕': ['꽃게탕'],
        '조림': ['꽃게조림'],
        '찜': ['꽃게찜'],
        '무침': ['꽃게무침'],
        '볶음': ['꽃게볶음'],
        '튀김': ['꽃게강정'],
        '기타(생식)': ['간장게장', '양념게장']
    },
    '새우': {
        '밥/죽': ['새우볶음밥'],
        '면류': ['새우크림파스타'],
        '국/탕': ['새우달걀국', '얼큰새우매운탕'],
        '조림': ['새우조림'],
        '찜': ['새우달걀찜'],
        '무침': ['새우젓'],
        '볶음': ['건새우볶음'],
        '부침': ['새우전'],
        '튀김': ['새우튀김'],
        '구이': ['새우버터구이'],
        '기타(생식)': ['간장새우장', '양념새우장']
    },
    '다슬기': {'면류': ['다슬기수제비'], '국/탕': ['다슬기된장국'], '무침': ['다슬기무침'], '부침': ['다슬기파전']},
    '꼬막': {
        '밥/죽': ['꼬막비빔밥'],
        '면류': ['꼬막칼국수'],
        '국/탕': ['꼬막된장찌개'],
        '찜': ['꼬막찜'],
        '무침': ['꼬막무침'],
        '부침': ['꼬막전'],
        '구이': ['꼬막떡꼬치구이']
    },
    '가리비': {
        '밥/죽': ['가리비초밥'],
        '면류': ['가리비칼국수'],
        '국/탕': ['가리비탕'],
        '찜': ['가리비찜'],
        '무침': ['가리비초무침'],
        '볶음': ['가리비볶음'],
        '구이': ['가리비버터구이']
    },
    '골뱅이': {
        '밥/죽': ['골뱅이죽'],
        '면류': ['골뱅이비빔면'],
        '국/탕': ['골뱅이탕'],
        '무침': ['골뱅이무침'],
        '볶음': ['골뱅이볶음'],
        '튀김': ['골뱅이튀김'],
        '구이': ['골뱅이꼬치구이'],
        '기타(생식)': ['골뱅이물회']
    },
    '굴': {
        '밥/죽': ['굴국밥'],
        '면류': ['굴칼국수', '굴짬뽕'],
        '국/탕': ['매생이굴국', '굴순두부찌개'],
        '조림': ['굴조림'],
        '찜': ['굴찜'],
        '무침': ['굴무침'],
        '볶음': ['굴볶음'],
        '부침': ['굴전'],
        '튀김': ['굴튀김'],
        '구이': ['굴구이'],
        '기타(생식)': ['생굴']
    },
    '미더덕': {
        '밥/죽': ['미더덕밥'],
        '국/탕': ['미더덕된장찌개', '미더덕순두부찌개'],
        '찜': ['미더덕콩나물찜']
    },
    '바지락': {
        '밥/죽': ['바지락비빔밥'],
        '면류': ['바지락칼국수'],
        '국/탕': ['바지락미역국', '바지락순두부찌개'],
        '찜': ['바지락찜'],
        '무침': ['바지락무침'],
        '볶음': ['바지락볶음', '매콤바지락볶음'],
        '부침': ['바지락부추전']
    },
    '백합': {
        '밥/죽': ['백합볶음밥'],
        '면류': ['백합칼국수'],
        '국/탕': ['백합탕'],
        '찜': ['백합찜'],
        '무침': ['백합무침'],
        '볶음': ['백합볶음'],
        '구이': ['백합구이']
    },
    '소라': {
        '밥/죽': ['참소라야채죽'],
        '면류': ['소라비빔면'],
        '국/탕': ['소라된장찌개'],
        '조림': ['참소라장조림'],
        '찜': ['소라숙회'],
        '무침': ['소라무침'],
        '볶음': ['소라버터볶음'],
        '튀김': ['소라튀김'],
        '구이': ['소라구이'],
        '기타(생식)': ['소라회']
    },
    '재첩': {'국/탕': ['재첩국'], '무침': ['재첩무침'], '부침': ['재첩부추전']},
    '전복': {
        '밥/죽': ['전복죽'],
        '면류': ['전복파스타'],
        '국/탕': ['전복미역국'],
        '조림': ['전복장조림'],
        '찜': ['전복찜'],
        '무침': ['전복무침'],
        '볶음': ['전복볶음'],
        '구이': ['전복구이'],
        '기타(생식)': ['전복회']
    },
    '홍합': {
        '밥/죽': ['홍합죽'],
        '면류': ['홍합칼국수', '홍합짬뽕'],
        '국/탕': ['홍합탕', '홍합된장찌개'],
        '조림': ['홍합조림'],
        '찜': ['홍합찜'],
        '무침': ['홍합무침'],
        '볶음': ['홍합볶음'],
        '부침': ['홍합전'],
        '구이': ['홍합구이']
    },
    '가자미': {
        '국/탕': ['가자미미역국'],
        '조림': ['가자미조림'],
        '찜': ['가자미찜'],
        '부침': ['가자미전'],
        '튀김': ['가자미튀김'],
        '구이': ['가자미구이']
    },
    '다랑어': {
        '밥/죽': ['참치김밥'],
        '국/탕': ['참치김치찌개'],
        '볶음': ['참치양배추볶음'],
        '부침': ['참치달걀말이'],
        '구이': ['참치스테이크'],
        '생식류/절임류/장류': ['참치회']
    },
    '고등어': {'조림': ['고등어조림'], '구이': ['고등어구이']},
    '갈치': {'조림': ['갈치조림'], '구이': ['갈치구이']},
    '꽁치': {'국/탕': ['꽁치김치찌개'], '조림': ['꽁치조림'], '구이': ['꽁치구이']},
    '대구': {'국/탕': ['맑은대구탕', '대구매운탕'], '조림': ['대구조림'], '부침': ['대구전']},
    '멸치': {'밥/죽': ['멸치김밥'], '볶음': ['멸치볶음']},
    '명태': {
        '국/탕': ['황태미역국'],
        '조림': ['코다리조림'],
        '찜': ['명태찜'],
        '무침': ['북어채무침'],
        '구이': ['코다리구이']
    },
    '박대': {'조림': ['박대조림'], '구이': ['박대구이']},
    '뱅어': {'무침': ['뱅어포무침'], '튀김': ['뱅어포튀김']},
    '병어': {'조림': ['병어조림'], '구이': ['병어구이']},
    '삼치': {'조림': ['삼치조림'], '튀김': ['삼치튀김'], '구이': ['삼치구이']},
    '아귀': {'국/탕': ['아귀탕'], '찜': ['아귀찜']},
    '연어': {'밥/죽': ['연어덮밥'], '구이': ['연어구이'], '생식류/절임류/장류': ['연어회']},
    '임연수': {'조림': ['임연수조림'], '구이': ['임연수구이']},
    '장어': {
        '밥/죽': ['장어덮밥'],
        '조림': ['장어조림'],
        '찜': ['장어찜'],
        '튀김': ['장어튀김'],
        '구이': ['장어구이']
    },
    '조기': {'조림': ['조기조림'], '찜': ['조기찜'], '구이': ['조기구이']}
}

INGREDIENT_CATEGORIES = [
    ("🍤 가공수산물", ['맛살', '어란', '어묵', '쥐포']),
    ("🌿 해조류", ['김', '다시마', '매생이', '미역', '파래', '톳']),
    ("🦑 연체류", ['꼴뚜기', '낙지', '문어', '오징어', '주꾸미']),
    ("🦀 갑각류", ['가재', '게', '새우']),
    ("🐚 패류", [
        '다슬기', '꼬막', '가리비', '골뱅이', '굴', '미더덕', '바지락', '백합',
        '소라', '재첩', '전복', '홍합'
    ]),
    ("🐟 어류", [
        '가자미', '다랑어', '고등어', '갈치', '꽁치', '대구', '멸치', '명태',
        '박대', '뱅어', '병어', '삼치', '아귀', '연어', '임연수', '장어', '조기'
    ])
]

TOTAL_CATEGORY_COUNT = len(INGREDIENT_CATEGORIES)


# ===================== 화이트리스트 체크 =====================

@st.cache_data(ttl=300)
def load_allowed_name_id_pairs():
    pairs = set()
    try:
        raw_pairs = st.secrets.get("allowed_pairs", None)
        if raw_pairs and isinstance(raw_pairs, (list, tuple)):
            for item in raw_pairs:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    nm = str(item[0]).strip()
                    idv = str(item[1]).strip().upper()
                    if nm and idv:
                        pairs.add((nm, idv))
    except Exception:
        pass
    try:
        sheet = get_google_sheet_cached()
        if sheet is not None:
            workbook = sheet.spreadsheet
            titles = [ws.title for ws in workbook.worksheets()]
            if "참여자_명단" in titles:
                w = workbook.worksheet("참여자_명단")
                rows = w.get_all_values()
                for r in rows[1:]:
                    if len(r) >= 2:
                        nm = str(r[0]).strip()
                        idv = str(r[1]).strip().upper()
                        if nm and idv:
                            pairs.add((nm, idv))
    except Exception:
        pass
    return pairs

def is_valid_name_id(name: str, id_number: str) -> bool:
    if not name or not id_number:
        return False
    allowed = load_allowed_name_id_pairs()
    if len(allowed) == 0:
        return True
    return (name.strip(), id_number.strip().upper()) in allowed


# ===================== 화면 1: 참여자 정보 입력 =====================

def show_info_form():
    st.markdown("# 🐟 블루푸드 선호도 조사")
    st.markdown("## 1단계: 참여자 정보 입력")
    st.markdown(
        """
        <p style="font-size:16px; line-height:1.5; color:#333;">
        설문 참여를 위해 성함과 식별번호를 입력해주세요.
        </p>
        """,
        unsafe_allow_html=True
    )

    with st.form("info_form"):
        name = st.text_input("성함", value=st.session_state.name, placeholder="홍길동", max_chars=20)
        id_number = st.text_input("식별번호", value=st.session_state.id_number, placeholder="예: HG001", max_chars=20)

        submitted = st.form_submit_button("다음 단계 →", use_container_width=True)
        if submitted:
            if not name or not id_number:
                st.error("성함과 식별번호를 모두 입력해주세요.")
            else:
                if not is_valid_name_id(name, id_number):
                    st.error("❌ 등록되지 않은 성함/식별번호입니다. 담당자로부터 받은 정보를 입력해주세요.")
                else:
                    st.session_state.name = name
                    st.session_state.id_number = id_number
                    st.session_state.step = 'guide'          # 👈 다음은 카테고리 단계
                    st.session_state.category_index = 0         # 첫 카테고리부터 시작
                    st.rerun()

# ===================== 화면 =====================
def show_overall_guide():
    st.markdown("# 🐟 블루푸드 선호도 조사")
    st.markdown("## 설문 안내")

    st.markdown(
        """
        <div style="font-size:16px; line-height:1.6; color:#333;">
        <p><strong>2단계 진행 방법</strong></p>
        <p>
        1) 아래 수산물(원재료) 중에서 드시기 편하신 것, 선호하시는 것을 모두 선택해주세요.<br>
        (각 카테고리는 아무 것도 선택하지 않으셔도 됩니다.)<br><br>

        2) 선택하신 재료가 있다면, 각각에 대해 즐겨 드시는 메뉴를 골라주세요.<br><br>

        ※ 전체 설문 기준으로는 <strong>최소 3개 이상</strong> 수산물을 선택 부탁드립니다.
        </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    # 버튼: 본 설문 시작
    if st.button("설문 시작하기 →", use_container_width=True, type="primary"):
        # 카테고리 루프 첫 번째로 이동
        st.session_state.step = "category_loop"
        st.session_state.category_index = 0
        st.rerun()


# ===================== 화면 2: 카테고리별 (재료 선택 + 메뉴 선택) =====================
def show_category_step():
    idx = st.session_state.category_index
    cat_label, ing_list = INGREDIENT_CATEGORIES[idx]

    st.markdown("# 블루푸드 선호도 조사")
    st.markdown(f"## 2단계: {cat_label} 선호도 조사")
    st.markdown(
        """
        <p style="font-size:16px; line-height:1.5; color:#333;">
        1) 아래 수산물(원재료) 중에서 드시기 편하신 것, 선호하시는 것을 모두 선택해주세요.<br>
        (이 카테고리는 아무 것도 선택하지 않으셔도 됩니다.)<br><br>
        2) 선택하신 재료가 있다면, 각각에 대해 즐겨 드시는 메뉴를 골라주세요.<br>
        <br>
        <strong>※ 전체 설문 기준으로는 최소 3개 이상 수산물을 선택 부탁드립니다.</strong>
        </p>
        """,
        unsafe_allow_html=True
    )

    # ---------- (1) 이 카테고리의 수산물 선택 영역 ----------
    st.markdown("###🐟 선호 수산물 선택")

    num_cols = 3
    cols = st.columns([1,1,1])

    for i, ing_name in enumerate(ing_list):
        col = cols[i % num_cols]
        with col:
            is_selected_globally = ing_name in st.session_state.selected_ingredients
            label = f"👍{ing_name}" if is_selected_globally else ing_name
            btn_type = "primary" if is_selected_globally else "secondary"

            if st.button(
                label,
                key=f"ing_{idx}_{ing_name}",
                use_container_width=True,
                type=btn_type
            ):
                # 토글
                if is_selected_globally:
                    st.session_state.selected_ingredients.remove(ing_name)
                    if ing_name in st.session_state.selected_menus:
                        del st.session_state.selected_menus[ing_name]
                else:
                    st.session_state.selected_ingredients.append(ing_name)
                    if ing_name not in st.session_state.selected_menus:
                        st.session_state.selected_menus[ing_name] = []
                st.rerun()

    # 현재까지 전체 누적 선택 수 안내
    total_selected_count = len(st.session_state.selected_ingredients)
    if total_selected_count < 3:
        box_msg = f"현재까지 전체 선택 수산물: {total_selected_count}개 · 최소 3개 이상 선택 부탁드립니다."
        box_style = "background-color:#fff3cd;border:1px solid #ffe69c;color:#664d03;"
    else:
        box_msg = f"현재까지 전체 선택 수산물: {total_selected_count}개"
        box_style = "background-color:#d1e7dd;border:1px solid #badbcc;color:#0f5132;"

    st.markdown(
        f"""
        <div style="{box_style}
            border-radius:8px;
            padding:12px 16px;
            font-size:16px;
            font-weight:500;
            margin:16px 0;">
            {box_msg}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    # ---------- (2) 메뉴 선택 영역 (조건부 렌더) ----------
    chosen_ings_in_this_cat = [
        ing for ing in ing_list
        if ing in st.session_state.selected_ingredients
    ]

    # flag: 이 카테고리에서 뭔가 재료는 골랐는지
    picked_any_here = len(chosen_ings_in_this_cat) > 0

    # 카테고리 유효성 체크용 (기본 True, 나중에 메뉴 없으면 False로 깎음)
    all_valid_this_cat = True

    if picked_any_here:
        # 👉 재료를 골랐을 때만 메뉴 영역을 그린다
        st.markdown("### 🐟 선호 메뉴 선택")
        st.markdown(
            """
            <p style="font-size:15px; line-height:1.5; color:#333; margin-top:-8px;">
            이 카테고리에서 선택하신 수산물이 있다면,<br>
            각 수산물마다 좋아하시는 조리 메뉴를 골라주세요.<br>
            <strong>각 수산물당 최소 1개 이상</strong> 선택 부탁드립니다.
            </p>
            """,
            unsafe_allow_html=True
        )

        for ing_idx_local, ing_name in enumerate(chosen_ings_in_this_cat):
            st.markdown(
                f"""
                <h4 style="margin-top:16px; margin-bottom:12px;
                           font-size:18px; font-weight:700; color:#000;">
                    🍽️ {ing_name} 메뉴
                </h4>
                """,
                unsafe_allow_html=True
            )

            # 가능한 메뉴들 수집
            all_menus = []
            if ing_name in MENU_DATA:
                for menu_list in MENU_DATA[ing_name].values():
                    all_menus.extend(menu_list)

            # 세션 키 보장
            if ing_name not in st.session_state.selected_menus:
                st.session_state.selected_menus[ing_name] = []

            # 메뉴 토글 버튼들
            cols_m = st.columns([1,1,1])
            for m_i, menu_name in enumerate(all_menus):
                colm = cols_m[m_i % 3]
                with colm:
                    is_menu_selected = menu_name in st.session_state.selected_menus[ing_name]
                    menu_label = f"✅ {menu_name}" if is_menu_selected else menu_name
                    menu_btn_type = "primary" if is_menu_selected else "secondary"

                    if st.button(
                        menu_label,
                        key=f"menu_{idx}_{ing_idx_local}_{m_i}_{menu_name}",
                        use_container_width=True,
                        type=menu_btn_type
                    ):
                        if is_menu_selected:
                            st.session_state.selected_menus[ing_name].remove(menu_name)
                        else:
                            st.session_state.selected_menus[ing_name].append(menu_name)
                        st.rerun()

            chosen_cnt = len(st.session_state.selected_menus.get(ing_name, []))
            if chosen_cnt == 0:
                all_valid_this_cat = False
                st.warning(f"{ing_name}: 최소 1개 이상의 메뉴를 선택해주세요.")
            else:
                st.success(f"{ing_name}: {chosen_cnt}개 메뉴 선택됨")

            st.markdown("<hr>", unsafe_allow_html=True)

    # ---------- (3) 하단 네비게이션 영역 ----------
    col_prev, col_mid, col_next = st.columns([1,1,1])

    with col_prev:
        disable_prev = (idx == 0)
        if st.button("← 이전", use_container_width=True, disabled=disable_prev):
            if idx > 0:
                st.session_state.category_index -= 1
                st.rerun()

    with col_mid:
        if st.button("현재 카테고리 선택 초기화", use_container_width=True):
            for ing_name in ing_list:
                if ing_name in st.session_state.selected_ingredients:
                    st.session_state.selected_ingredients.remove(ing_name)
                if ing_name in st.session_state.selected_menus:
                    del st.session_state.selected_menus[ing_name]
            st.rerun()

    with col_next:
        is_last_category = (idx == TOTAL_CATEGORY_COUNT - 1)

        # picked_any_here = 이번 카테고리에서 최소 1개 재료는 골랐는지
        # all_valid_this_cat = (재료를 골랐다면) 그 재료별로 메뉴도 최소 1개 이상 골랐는지
        if picked_any_here:
            cat_ready = all_valid_this_cat
        else:
            cat_ready = True  # 이번 카테고리 자체는 패스 가능

        # 마지막 제출 시에는 전체 수산물 최소 3개 이상
        global_ready = (len(st.session_state.selected_ingredients) >= 3)

        next_btn_label = "설문 완료하기 ✅" if is_last_category else "다음 카테고리 →"

        if is_last_category:
            final_disabled = not (cat_ready and global_ready)
        else:
            final_disabled = not cat_ready

        if st.button(next_btn_label, use_container_width=True, disabled=final_disabled):
            if is_last_category:
                # 저장 & 완료화면
                filename, df = save_to_excel(
                    st.session_state.name,
                    st.session_state.id_number,
                    st.session_state.selected_ingredients,
                    st.session_state.selected_menus
                )
                save_to_google_sheets(
                    st.session_state.name,
                    st.session_state.id_number,
                    st.session_state.selected_ingredients,
                    st.session_state.selected_menus
                )
                if filename is not None or st.session_state.get("google_sheets_success", False):
                    st.session_state.already_saved = True
                    st.session_state.filename = filename
                    st.session_state.survey_data = df
                    st.session_state.step = 'complete'
                    st.rerun()
                else:
                    st.error("❌ 설문 데이터 저장에 실패했습니다. 다시 시도해주세요.")
            else:
                st.session_state.category_index += 1
                st.rerun()

# ===================== 화면 3: 완료 =====================

def show_completion():
    st.success("🎉 설문이 완료되었습니다! 감사합니다.")

    if st.session_state.google_sheets_success:
        st.success("✅ 데이터가 Google Sheets에 저장되었습니다!")
    else:
        st.warning("⚠️ Google Sheets 연결에 문제가 있어 로컬 백업 파일에 저장되었습니다.")

    st.markdown(f"**참여자:** {st.session_state.name}")
    st.markdown(f"**식별번호:** {st.session_state.id_number}")
    st.markdown(f"**설문 완료 시간:** {format_korean_time()}")

    st.markdown("### 선택하신 수산물")
    st.markdown(" | ".join(st.session_state.selected_ingredients))

    st.markdown("### 선호하시는 메뉴")
    for ing_name, menus in st.session_state.selected_menus.items():
        if menus:
            st.markdown(f"**{ing_name}:** {', '.join(menus)}")

    # 관리자 전용 로컬 엑셀 다운로드
    if st.session_state.is_admin and st.session_state.get("filename"):
        if os.path.exists(st.session_state.filename):
            with open(st.session_state.filename, 'rb') as file:
                st.download_button(
                    label="📥 백업 파일 다운로드 (관리자 전용)",
                    data=file.read(),
                    file_name=f"bluefood_survey_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    type="primary",
                    use_container_width=True
                )

    # 새 설문 시작 버튼
    if st.button("🔄 새 설문 시작하기", use_container_width=True):
        admin_status = st.session_state.is_admin
        admin_login_status = st.session_state.show_admin_login

        keys_to_keep = ['is_admin', 'show_admin_login']
        for key in list(st.session_state.keys()):
            if key not in keys_to_keep:
                del st.session_state[key]

        st.session_state.is_admin = admin_status
        st.session_state.show_admin_login = admin_login_status
        st.session_state.step = 'info'
        st.session_state.name = ""
        st.session_state.id_number = ""
        st.session_state.selected_ingredients = []
        st.session_state.selected_menus = {}
        st.session_state.google_sheets_success = False
        st.session_state.already_saved = False
        st.session_state.category_index = 0
        st.rerun()


# ===================== 메인 =====================

def main():
    # ===== 사이드바 =====
    with st.sidebar:
        # 연구/과제 정보 카드
        st.markdown(
            """
            <div style="
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                padding: 16px;
                border-radius: 12px;
                margin-bottom: 16px;
                color: white;
                box-shadow: 0 4px 10px rgba(0,0,0,0.15);
                font-size:16px;
                line-height:1.4;
            ">
                <div style="font-size:18px;font-weight:700;text-align:center;margin-bottom:8px;">
                    📌 연구 정보
                </div>
                <div style="background: rgba(255,255,255,0.15); padding:8px; border-radius:8px; margin-bottom:8px;">
                    <strong>🔹 연구명</strong><br>
                    요양원 거주 고령자 대상 건강 상태 및<br>블루푸드 식이 데이터베이스 구축
                </div>
                <div style="background: rgba(255,255,255,0.15); padding:8px; border-radius:8px; margin-bottom:8px;">
                    <strong>🔹 정부과제명</strong><br>
                    글로벌 블루푸드 미래리더 양성 프로젝트
                </div>
                <div style="background: rgba(255,255,255,0.15); padding:8px; border-radius:8px;">
                    <strong>🔹 연구 담당자</strong><br>
                    류혜리, 유정연<br>(서울대학교 농생명공학부 박사과정)
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 관리자 로그인 / 대시보드
        st.markdown("---")
        if not st.session_state.is_admin:
            if st.button("🔐 관리자 로그인", use_container_width=True):
                st.session_state.show_admin_login = True
                st.rerun()
            if st.session_state.show_admin_login:
                with st.form("admin_login"):
                    password = st.text_input("관리자 패스워드", type="password")
                    login_btn = st.form_submit_button("로그인")
                    if login_btn:
                        if password == ADMIN_PASSWORD:
                            st.session_state.is_admin = True
                            st.session_state.show_admin_login = False
                            st.success("관리자로 로그인되었습니다!")
                            st.rerun()
                        else:
                            st.error("잘못된 패스워드입니다.")
        else:
            st.success("🔐 관리자 모드")
            backup_files = ["bluefood_survey.xlsx", "bluefood_survey_backup.xlsx"]
            available_file = None
            for file in backup_files:
                if os.path.exists(file):
                    available_file = file
                    break

            if available_file:
                with open(available_file, 'rb') as file:
                    st.download_button(
                        label="📥 전체 설문 데이터 다운로드",
                        data=file.read(),
                        file_name=f"bluefood_survey_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        use_container_width=True
                    )

                try:
                    df = pd.read_excel(available_file)
                    st.markdown(f"**📊 총 응답 수: {len(df)}건**")
                    if '설문일시' in df.columns:
                        st.markdown(f"**📅 최근 응답: {df['설문일시'].max()}**")
                    
                    # 간단 요약만: 여기선 전체 대시보드까지는 안 보여줘도 되지만
                    # 원하면 show_admin_dashboard(df) 호출 가능
                    # show_admin_dashboard(df)
                except Exception:
                    st.markdown("**📊 데이터 로드 오류**")
            else:
                st.info("아직 설문 데이터가 없습니다.")

            if st.button("🚪 로그아웃", use_container_width=True):
                st.session_state.is_admin = False
                st.session_state.show_admin_login = False
                st.rerun()

        # 설문 안내 (업데이트된 단계 설명)
        current_cat_num = st.session_state.category_index + 1 if st.session_state.step == 'category' else 0
        st.markdown(
            f"""
            <div style="
                background:#ffffff;
                padding:16px;
                border-radius:12px;
                margin-bottom:16px;
                color:#333;
                font-size:16px;
                line-height:1.5;
                box-shadow:0 4px 10px rgba(0,0,0,0.1);
                border:1px solid #ddd;
            ">
                <div style="font-size:18px;font-weight:700;color:#0077b6;text-align:center;margin-bottom:8px;">
                    📋 설문 안내
                </div>
                <p><strong>🎯 목적</strong><br>블루푸드 선호도 조사</p>
                <p><strong>⏱️ 소요</strong><br>약 3-5분</p>
                <p><strong>📝 설문 방식</strong><br>
                    1️⃣ 참여자 정보 입력<br>
                    2️⃣ 카테고리별로<br>
                    &nbsp;&nbsp;• 선호 수산물 선택 →<br>
                    &nbsp;&nbsp;• 그 수산물 메뉴 선택<br>
                    3️⃣ 완료
                </p>
                <p><strong>현재 진행 카테고리:</strong><br>
                    {current_cat_num} / {TOTAL_CATEGORY_COUNT if TOTAL_CATEGORY_COUNT else '-'}
                </p>
                <p><strong>🔒 개인정보 보호</strong><br>
                    수집된 정보는 연구 목적으로만 사용되며,<br>
                    개인정보는 안전하게 보호됩니다.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 진행 상황 바
        st.markdown("### 📊 진행 상황")
        if st.session_state.step == 'info':
            st.progress(0.2, "1단계: 정보 입력")
        elif st.session_state.step == 'guide':
            st.progress(0.3, "2단계: 설문 안내")
        elif st.session_state.step == 'category_loop':
            st.progress(0.7, "3단계: 선호 식재료 & 메뉴 선택")
        elif st.session_state.step == 'complete':
            st.progress(1.0, "✅ 설문 완료!")

    # ===== 메인 영역 단계 전환 =====
    if st.session_state.step == 'info':
        show_info_form()
    elif st.session_state.step == 'guide':
        show_overall_guide()
    elif st.session_state.step == 'category_loop':
        show_category_step()
    elif st.session_state.step == 'complete':
        show_completion()


if __name__ == "__main__":
    main()
