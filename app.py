import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import gspread
import os
import traceback
from google.oauth2.service_account import Credentials
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib as mpl
import matplotlib.font_manager as fm
from matplotlib import rcParams
import urllib.request

# ===================== 기본 설정 =====================

# 라이트 모드 강제 (모바일에서 다크/라이트 전환 때문에 대비가 깨지는 문제 방지)
LIGHT_FORCE_CSS = """
<style>
/* 전체 라이트 모드 강제 */
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

/* 그리드: 한 줄에 4개. 화면이 좁아지면 자동으로 다음 줄로 떨어짐 */
.ingredient-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);  /* <- 핵심!! 4등분 */
    grid-gap: 8px;
    margin-bottom: 12px;
}

/* 카드 하나 (식재료용) */
.card-box {
    border: 2px solid #666666;
    background-color: #ffffff;
    color: #000000;
    border-radius:10px;
    padding:12px 6px;
    min-height:64px;
    display:flex;
    align-items:center;
    justify-content:center;
    text-align:center;
    font-size:15px;
    font-weight:600;
    line-height:1.3;
    word-break: keep-all;
}
.card-box.selected {
    background-color: #00b4d8;
    border-color: #0096c7;
    color: #ffffff;
}

/* 체크박스는 화면에서 숨김 (state만 유지) */
.hidden-check {
    display:none;
}

/* 메뉴 카드 (2단계 화면) 기존 유지 */
.menu-card-box {
    border: 2px solid #666666;
    background-color: #ffffff;
    color: #000000;
    border-radius:10px;
    padding:16px 10px;
    min-height:80px;
    display:flex;
    align-items:center;
    justify-content:center;
    text-align:center;
    font-size:18px;
    font-weight:600;
    line-height:1.3;
    word-break: keep-all;
}
.menu-card-box.selected {
    background-color: #00b4d8;
    border-color: #0096c7;
    color: #ffffff;
}
</style>
"""
st.set_page_config(
    page_title="블루푸드 선호도 조사",
    page_icon="🐟",
    layout="wide"
)
st.markdown(LIGHT_FORCE_CSS, unsafe_allow_html=True)

# ===================== 폰트(한글 깨짐 방지) =====================
# NanumGothic 폰트 설정
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


# ===================== Google Sheets 연결 =====================

def get_google_sheet_cached():
    """Google Sheets 연결 (간단/안정화 버전)"""
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

        # 헤더 확인
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
    """Google Sheets 저장 (에러 나도 앱은 계속 진행)"""
    if st.session_state.get("already_saved", False):
        return True

    try:
        sheet = get_google_sheet_cached()
        if sheet is None:
            return False

        import json
        menus_text = json.dumps(selected_menus, ensure_ascii=False)
        ingredients_text = ', '.join(selected_ingredients)
        current_time = format_korean_time()

        row_data = [name, id_number, current_time, ingredients_text, menus_text]
        sheet.append_row(row_data, value_input_option="RAW")

        st.session_state.google_sheets_success = True
        st.session_state.already_saved = True
        return True
    except Exception as e:
        st.session_state.google_sheets_success = False
        return False


def save_to_excel(name, id_number, selected_ingredients, selected_menus):
    """로컬 엑셀 백업 저장"""
    if st.session_state.get("already_saved", False):
        return "skipped", None

    # 구글시트는 시도만 (성공/실패 상관없이 저장 계속)
    save_to_google_sheets(name, id_number, selected_ingredients, selected_menus)

    try:
        new_data = {
            '이름': name,
            '식별번호': id_number,
            '설문일시': format_korean_time(),
            '선택한_수산물': ', '.join(selected_ingredients),
            '선택한_메뉴': ', '.join([
                f"{ingredient}: {', '.join(menus)}"
                for ingredient, menus in selected_menus.items()
            ])
        }

        for ingredient in selected_ingredients:
            new_data[f'{ingredient}_메뉴'] = ', '.join(
                st.session_state.selected_menus.get(ingredient, [])
            )

        new_df = pd.DataFrame([new_data])
        filename = "bluefood_survey.xlsx"

        if os.path.exists(filename):
            old_df = pd.read_excel(filename)
            final_df = pd.concat([old_df, new_df], ignore_index=True)
        else:
            final_df = new_df

        final_df.to_excel(filename, index=False)
        return filename, final_df

    except Exception as e:
        st.error(f"❌ 로컬 엑셀 저장 실패: {e}")
        return None, None


# ===================== 세션 상태 초기화 =====================

if 'step' not in st.session_state:
    st.session_state.step = 'info'
if 'selected_ingredients' not in st.session_state:
    st.session_state.selected_ingredients = []
if 'selected_menus' not in st.session_state:
    st.session_state.selected_menus = {}
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'show_admin_login' not in st.session_state:
    st.session_state.show_admin_login = False
if 'already_saved' not in st.session_state:
    st.session_state.already_saved = False


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

INGREDIENT_CATEGORIES = {
    '🍤 가공수산물': ['맛살', '어란', '어묵', '쥐포'],
    '🌿 해조류': ['김', '다시마', '매생이', '미역', '파래', '톳'],
    '🦑 연체류': ['꼴뚜기', '낙지', '문어', '오징어', '주꾸미'],
    '🦀 갑각류': ['가재', '게', '새우'],
    '🐚 패류': [
        '다슬기', '꼬막', '가리비', '골뱅이', '굴', '미더덕', '바지락', '백합',
        '소라', '재첩', '전복', '홍합'
    ],
    '🐟 어류': [
        '가자미', '다랑어', '고등어', '갈치', '꽁치', '대구', '멸치', '명태',
        '박대', '뱅어', '병어', '삼치', '아귀', '연어', '임연수', '장어', '조기'
    ]
}

# ===================== 참여자 화이트리스트 체크 =====================

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
    # Google Sheets 참여자_명단 시트도 있으면 읽기
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
    return (name.strip(), id_number.strip().upper()) in allowed


# ===================== UI 컴포넌트 함수들 =====================

def show_admin_dashboard(df):
    """관리자용 간단 대시보드 (폰트 세팅 포함)"""
    st.markdown("## 📊 관리자 대시보드")

    if df is None or df.empty:
        st.warning("⚠️ 응답 데이터가 없습니다.")
        return

    st.markdown(f"**총 응답자 수:** {df['식별번호'].nunique()}명")
    st.markdown(f"**총 응답 수:** {len(df)}건")
    st.markdown(f"**최근 응답 시간:** {df['설문일시'].max()}")

    # 중복 응답 검사
    st.markdown("### 🔍 중복 응답 감지")
    dup = df[df.duplicated('식별번호', keep=False)]
    if not dup.empty:
        st.warning(f"⚠️ {dup['식별번호'].nunique()}명의 중복 응답 발견")
        st.dataframe(dup)
    else:
        st.success("✅ 중복 응답 없음")

    # 수산물 TOP5
    if '선택한_수산물' in df.columns:
        st.markdown("### 🐟 수산물 선호도 TOP5")
        try:
            all_ingredients = (
                df['선택한_수산물']
                .dropna()
                .astype(str)
                .str.split(',')
                .explode()
                .str.strip()
            )
            top_ing = all_ingredients.value_counts().head(5)
            if not top_ing.empty:
                fig1, ax1 = plt.subplots()
                sns.barplot(
                    x=top_ing.values,
                    y=top_ing.index,
                    ax=ax1,
                )
                if fontprop:
                    ax1.set_title("선호 수산물 TOP5", fontproperties=fontprop)
                    ax1.set_xlabel("응답 수", fontproperties=fontprop)
                    ax1.set_ylabel("수산물", fontproperties=fontprop)
                    for label in ax1.get_yticklabels():
                        label.set_fontproperties(fontprop)
                    for label in ax1.get_xticklabels():
                        label.set_fontproperties(fontprop)
                st.pyplot(fig1)
        except Exception as e:
            st.error(f"데이터 로드 오류 (수산물): {e}")

    # 메뉴 TOP5
    st.markdown("### 🍽️ 메뉴 선호도 TOP5")
    if '선택한_메뉴' in df.columns:
        try:
            menu_list = []
            for menus in df['선택한_메뉴'].dropna():
                for item in str(menus).split(","):
                    if ":" in item:
                        menu_list.append(item.split(":", 1)[1].strip())
                    else:
                        menu_list.append(item.strip())

            if menu_list:
                menu_series = pd.Series(menu_list)
                top_menu = menu_series.value_counts().head(5)

                fig2, ax2 = plt.subplots()
                sns.barplot(
                    x=top_menu.values,
                    y=top_menu.index,
                    ax=ax2,
                )
                if fontprop:
                    ax2.set_title("선호 메뉴 TOP5", fontproperties=fontprop)
                    ax2.set_xlabel("응답 수", fontproperties=fontprop)
                    ax2.set_ylabel("메뉴", fontproperties=fontprop)
                    for label in ax2.get_yticklabels():
                        label.set_fontproperties(fontprop)
                    for label in ax2.get_xticklabels():
                        label.set_fontproperties(fontprop)
                st.pyplot(fig2)
        except Exception as e:
            st.error(f"데이터 로드 오류 (메뉴): {e}")

    # 날짜별 추이
    if '설문일시' in df.columns:
        st.markdown("### ⏱️ 날짜별 응답 추이")
        try:
            df['설문일자'] = pd.to_datetime(df['설문일시'], errors='coerce').dt.date
            daily_count = df.groupby('설문일자').size().reset_index(name='응답수')
            if not daily_count.empty:
                fig3, ax3 = plt.subplots()
                ax3.plot(daily_count['설문일자'], daily_count['응답수'], marker='o')
                if fontprop:
                    ax3.set_title("날짜별 응답 추이", fontproperties=fontprop)
                    ax3.set_xlabel("날짜", fontproperties=fontprop)
                    ax3.set_ylabel("응답 수", fontproperties=fontprop)
                ax3.grid(True, linestyle="--", alpha=0.5)
                fig3.autofmt_xdate()
                st.pyplot(fig3)
        except Exception as e:
            st.error(f"데이터 로드 오류 (날짜): {e}")


def show_info_form():
    st.subheader("📝 참여자 정보 입력")
    st.markdown(
        """
        <p style="font-size:16px; line-height:1.5; color:#333;">
        설문 참여를 위해 성함과 식별번호를 입력해주세요.
        </p>
        """,
        unsafe_allow_html=True
    )
    with st.form("info_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("성함", placeholder="홍길동", max_chars=20)
        with col2:
            id_number = st.text_input("식별번호", placeholder="예: HG001", max_chars=20)

        submitted = st.form_submit_button("설문 시작하기", use_container_width=True)
        if submitted:
            if name and id_number:
                if not is_valid_name_id(name, id_number):
                    st.error("❌ 등록되지 않은 성함/식별번호입니다. 담당자로부터 받은 정보를 입력해주세요.")
                    return
                st.session_state.name = name
                st.session_state.id_number = id_number
                st.session_state.step = 'ingredients'
                st.rerun()
            else:
                st.error("성함과 식별번호를 모두 입력해주세요.")


def ingredient_card_block(ingredient_name: str, is_selected: bool, key_suffix: str):
    """
    한 개 재료 카드 + 숨은 체크박스 (단일 셀용)
    Streamlit column 안에서 호출되는 버전
    """
    card_class = "card-box selected" if is_selected else "card-box"
    card_id = f"card_{key_suffix}"

    # 카드 HTML
    st.markdown(
        f"""
        <div id="{card_id}"
             class="{card_class}"
             onclick="document.getElementById('{card_id}_chk').click();"
             style="cursor:pointer; width:100%; height:100%;">
            <div class="card-label">{ingredient_name}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 실제 체크박스 (state 유지용)
    new_val = st.checkbox(
        "선택",
        value=is_selected,
        key=f"{card_id}_chk",
        label_visibility="collapsed"
    )

    # 체크박스 숨기기 (시각적으로만 감추고 상태는 유지)
    st.markdown(
        f"""
        <style>
        div[data-testid="stCheckbox"][class*="{card_id}_chk"] {{
            display:none !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

    return new_val


def show_ingredient_selection():
    # 상단 타이틀/설명
    st.title("🐟 블루푸드 선호도 조사")
    st.subheader("🐟 수산물 원재료 선호도")
    st.markdown(
        """
        <p style="font-size:16px; line-height:1.5; color:#333;">
        최소 3개 이상, 최대 9개까지 선택해주세요.
        </p>
        """,
        unsafe_allow_html=True
    )

    # 현재 선택 개수 안내 박스
    selected_count = len(st.session_state.selected_ingredients)
    if selected_count < 3:
        status_msg = f"현재 {selected_count}개 선택됨 · 최소 3개 이상 선택해주세요"
        status_class = "background-color:#fff3cd;border:1px solid #ffe69c;color:#664d03;"
    elif selected_count > 9:
        status_msg = f"현재 {selected_count}개 선택됨 · 최대 9개까지만 가능합니다"
        status_class = "background-color:#f8d7da;border:1px solid #f5c2c7;color:#842029;"
    else:
        status_msg = f"현재 {selected_count}개 선택됨"
        status_class = "background-color:#d1e7dd;border:1px solid #badbcc;color:#0f5132;"

    st.markdown(
        f"""
        <div style="
            {status_class}
            border-radius:8px;
            padding:12px 16px;
            font-size:16px;
            font-weight:500;
            margin-bottom:16px;">
            {status_msg}
        </div>
        """,
        unsafe_allow_html=True
    )

    # 카테고리 탭
    category_names = list(INGREDIENT_CATEGORIES.keys())
    tabs = st.tabs(category_names)

    for tab, category in zip(tabs, category_names):
        with tab:
            # 카테고리 제목
            st.markdown(
                f"""
                <h3 style="margin-top:8px; margin-bottom:12px;
                           font-size:20px; font-weight:700; color:#000;">
                    {category}
                </h3>
                """,
                unsafe_allow_html=True
            )

            ingredients = INGREDIENT_CATEGORIES[category]

            # 이 탭에서 변경된 값들 잠깐 담았다가 한 번에 세션에 반영
            local_updates = {}

            # 4개씩 가로 배치
            for row_start in range(0, len(ingredients), 4):
                row_items = ingredients[row_start:row_start+4]

                cols = st.columns(len(row_items))
                for col, ing_name in zip(cols, row_items):
                    with col:
                        is_selected = ing_name in st.session_state.selected_ingredients

                        # 카드 렌더 + 체크 상태 반환
                        new_val = ingredient_card_block(
                            ingredient_name=ing_name,
                            is_selected=is_selected,
                            key_suffix=f"{category}_{ing_name}"
                        )

                        local_updates[ing_name] = new_val

            # 이제 local_updates를 기반으로 session_state.selected_ingredients 수정
            for ing_name, new_val in local_updates.items():
                already = ing_name in st.session_state.selected_ingredients

                if new_val and not already:
                    # 새로 선택
                    if len(st.session_state.selected_ingredients) < 9:
                        st.session_state.selected_ingredients.append(ing_name)
                        if ing_name not in st.session_state.selected_menus:
                            st.session_state.selected_menus[ing_name] = []
                    else:
                        st.warning("최대 9개까지만 선택할 수 있습니다.")

                elif (not new_val) and already:
                    # 선택 해제
                    st.session_state.selected_ingredients.remove(ing_name)
                    # 필요하면 메뉴도 같이 비우기 가능

            # 이 카테고리 요약
            cat_selected = [
                x for x in st.session_state.selected_ingredients if x in ingredients
            ]
            if len(cat_selected) == 0:
                st.info("이 카테고리에서 아직 선택한 항목이 없습니다.")
            else:
                st.success("이 카테고리에서 선택됨: " + " / ".join(cat_selected))

    # 하단 구분선
    st.markdown("<hr style='margin-top:24px;margin-bottom:16px;'>", unsafe_allow_html=True)

    # 하단 버튼 영역
    col_left, col_mid, col_right = st.columns([1,1,1])

    with col_left:
        if st.button("선택 초기화", use_container_width=True):
            st.session_state.selected_ingredients = []
            st.session_state.selected_menus = {}
            st.rerun()

    with col_mid:
        st.write(f"현재 {len(st.session_state.selected_ingredients)}개")

    with col_right:
        can_go_next = (3 <= len(st.session_state.selected_ingredients) <= 9)
        if st.button("다음 단계 →", use_container_width=True, disabled=not can_go_next):
            if can_go_next:
                # 메뉴 dict shape 보장
                st.session_state.selected_menus = {
                    ing: st.session_state.selected_menus.get(ing, [])
                    for ing in st.session_state.selected_ingredients
                }
                st.session_state.step = 'menus'
                st.rerun()

st.markdown(
    """
    <script>
    // 폼 submit 직전에 선택값을 hidden필드에 반영
    // Streamlit의 form_submit_button은 실제로 <button type="submit">라서
    // 'click' 이벤트를 가로채는 식으로 넣을 수 있다.
    document.addEventListener("click", function(e){
        // "선택 초기화" 또는 "다음 단계 →" 눌렀을 때만 실행되면 충분
        if(e.target && e.target.innerText && (e.target.innerText.includes("다음 단계") || e.target.innerText.includes("선택 초기화"))){
            // 1. 현재 체크된 재료들 전부 수집
            const checkedVals = [];
            document.querySelectorAll('input[id^="ing_chk_"]').forEach(cb => {
                if(cb.checked){
                    checkedVals.push(cb.value);
                }
            });

            // 2. hidden text_input DOM 찾아서 값 업데이트
            // Streamlit은 text_input을 <input> 으로 렌더하니까 라벨 텍스트로 못 찾고
            // placeholder도 없으니 name 속성을 못 믿는다.
            // 우리는 'CHOSEN_INGREDIENTS_SYNC' 라는 value가 들어있는 input을 찾아서 업데이트하는 식으로 간단하게 처리한다.
            const candidates = Array.from(document.querySelectorAll('input'));
            const target = candidates.find(el => el.value === "%s");
            if(target){
                target.value = checkedVals.join(",");
            } else {
                // fallback: text_input의 aria-label 사용 시도
                const ariaTarget = candidates.find(el => el.getAttribute("aria-label")==="CHOSEN_INGREDIENTS_SYNC");
                if(ariaTarget){
                    ariaTarget.value = checkedVals.join(",");
                }
            }
        }
    });
    </script>
    """ % (",".join(st.session_state.selected_ingredients)),
    unsafe_allow_html=True
)

def menu_card_block_html(menu_name: str, is_selected: bool, idx: int, ing_name: str):
    """
    메뉴 선택 카드 (2단계). 구조는 ingredient_card_block_html와 유사.
    """
    card_class = "menu-card-box selected" if is_selected else "menu-card-box"
    card_id = f"menu_{ing_name}_{idx}"

    html = f"""
    <div id="{card_id}"
         class="{card_class}"
         onclick="document.getElementById('{card_id}_chk').click();"
         style="cursor:pointer;margin-bottom:8px;">
        <div class="card-label">{menu_name}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    new_val = st.checkbox(
        "선택",
        value=is_selected,
        key=f"{card_id}_chk",
        label_visibility="collapsed"
    )
    return new_val


def show_menu_selection():
    st.subheader("🍽️ 선호 메뉴 선택")
    st.markdown(
        """
        <p style="font-size:16px; line-height:1.5; color:#333;">
        선택하신 수산물로 만든 요리 중 선호하는 메뉴를 선택해주세요.<br>
        각 수산물마다 최소 1개 이상 선택해주세요.
        </p>
        """,
        unsafe_allow_html=True
    )

    all_valid = True

    # 각 재료별 섹션
    for ing_name in st.session_state.selected_ingredients:
        st.markdown(
            f"""
            <h3 style="margin-top:16px; margin-bottom:12px;
                       font-size:20px; font-weight:700; color:#000;">
                🐟 {ing_name} 요리
            </h3>
            """,
            unsafe_allow_html=True
        )

        # 가능한 메뉴들 flat
        all_menus = []
        if ing_name in MENU_DATA:
            for menu_list in MENU_DATA[ing_name].values():
                all_menus.extend(menu_list)

        local_updates = {}

        for idx, menu_name in enumerate(all_menus):
            is_selected = menu_name in st.session_state.selected_menus.get(ing_name, [])
            with st.container():
                new_val = menu_card_block_html(
                    menu_name=menu_name,
                    is_selected=is_selected,
                    idx=idx,
                    ing_name=ing_name
                )
                local_updates[menu_name] = new_val

        # 업데이트 반영
        for menu_name, new_val in local_updates.items():
            already = menu_name in st.session_state.selected_menus.get(ing_name, [])
            if new_val and not already:
                st.session_state.selected_menus[ing_name].append(menu_name)
            elif (not new_val) and already:
                st.session_state.selected_menus[ing_name].remove(menu_name)

        # 최소 1개 이상 선택 여부
        menu_count = len(st.session_state.selected_menus.get(ing_name, []))
        if menu_count == 0:
            all_valid = False
            st.warning(f"{ing_name}에 대해 최소 1개 이상의 메뉴를 선택해주세요.")
        else:
            st.success(f"{ing_name}: {menu_count}개 메뉴 선택됨")

        st.markdown("<hr>", unsafe_allow_html=True)

    # 하단 이동 버튼
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        if st.button("← 이전 단계", use_container_width=True):
            st.session_state.step = 'ingredients'
            st.rerun()
    with col3:
        if st.button("설문 완료하기", use_container_width=True, disabled=not all_valid):
            if all_valid:
                filename, df = save_to_excel(
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


def show_completion():
    st.balloons()
    st.success("🎉 설문이 완료되었습니다! 감사합니다.")

    if hasattr(st.session_state, 'google_sheets_success') and st.session_state.google_sheets_success:
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

    # 관리자만 다운로드 버튼
    if st.session_state.is_admin and 'filename' in st.session_state and st.session_state.filename:
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

    # 새 설문 시작
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
        st.session_state.selected_ingredients = []
        st.session_state.selected_menus = {}
        st.session_state.already_saved = False
        st.rerun()


def main():
    # 사이드바 (관리자 UI + 안내)
    with st.sidebar:
        # 연구 정보 카드
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

        # 관리자 로그인
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
                    st.markdown(f"**📊 총 응답자: {len(df)}명**")
                    if '설문일시' in df.columns:
                        st.markdown(f"**📅 최근 응답: {df['설문일시'].max()}**")
                    show_admin_dashboard(df)
                except Exception:
                    st.markdown("**📊 데이터 로드 오류**")
            else:
                st.info("아직 설문 데이터가 없습니다.")

            if st.button("🚪 로그아웃", use_container_width=True):
                st.session_state.is_admin = False
                st.session_state.show_admin_login = False
                st.rerun()

        # 설문 안내
        st.markdown(
            """
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
                <p><strong>⏱️ 소요시간</strong><br>약 3-5분</p>
                <p><strong>📝 설문 단계</strong><br>
                    1️⃣ 참여자 정보 입력<br>
                    2️⃣ 선호 수산물 선택 (3-9개)<br>
                    3️⃣ 선호 메뉴 선택<br>
                    4️⃣ 완료
                </p>
                <p><strong>🔒 개인정보 보호</strong><br>
                    수집된 정보는 연구 목적으로만 사용되며,<br>
                    개인정보는 안전하게 보호됩니다.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 진행 상황
        st.markdown("### 📊 진행 상황")
        if st.session_state.step == 'info':
            st.progress(0.25, "1단계: 정보 입력")
        elif st.session_state.step == 'ingredients':
            st.progress(0.5, "2단계: 수산물 선택")
        elif st.session_state.step == 'menus':
            st.progress(0.75, "3단계: 메뉴 선택")
        elif st.session_state.step == 'complete':
            st.progress(1.0, "✅ 설문 완료!")

    # 메인 화면 단계 전환
    if st.session_state.step == 'info':
        show_info_form()
    elif st.session_state.step == 'ingredients':
        show_ingredient_selection()
    elif st.session_state.step == 'menus':
        show_menu_selection()
    elif st.session_state.step == 'complete':
        show_completion()


if __name__ == "__main__":
    main()
