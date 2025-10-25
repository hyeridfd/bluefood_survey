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

# -------------------------------------------------
# 🔧 환경 플래그: 모바일 모드
# -------------------------------------------------
MOBILE_MODE = True  # 모바일 최적화 전용 화면으로 렌더링


# -------------------------------------------------
# ✅ 한글 폰트 설정 (관리자 대시보드 차트용)
# -------------------------------------------------
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


# -------------------------------------------------
# ✅ 관리자 대시보드 (데이터 현황 / 중복 / 차트)
# -------------------------------------------------
def show_admin_dashboard(df):
    st.markdown("## 📊 관리자 대시보드")

    if df is None or df.empty:
        st.warning("⚠️ 응답 데이터가 없습니다.")
        return

    st.markdown(f"**총 응답자 수:** {df['식별번호'].nunique()}명")
    st.markdown(f"**총 응답 수:** {len(df)}건")
    st.markdown(f"**최근 응답 시간:** {df['설문일시'].max()}")

    # 중복 응답 감지
    st.markdown("### 🔍 중복 응답 감지")
    dup = df[df.duplicated('식별번호', keep=False)]
    if not dup.empty:
        st.warning(f"⚠️ {dup['식별번호'].nunique()}명의 중복 응답 발견")
        st.dataframe(dup)
    else:
        st.success("✅ 중복 응답 없음")

    # 수산물 TOP5
    st.markdown("### 🐟 수산물 선호도 TOP5")
    if '선택한_수산물' in df.columns:
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
                    palette=["#A7C7E7", "#89CFF0", "#7EC8E3", "#5DADE2", "#3498DB"]
                )
                try:
                    ax1.set_title("선호 수산물 TOP5", fontproperties=fontprop)
                    ax1.set_xlabel("응답 수", fontproperties=fontprop)
                    ax1.set_ylabel("수산물", fontproperties=fontprop)
                    for label in ax1.get_yticklabels():
                        label.set_fontproperties(fontprop)
                    for label in ax1.get_xticklabels():
                        label.set_fontproperties(fontprop)
                except NameError:
                    ax1.set_title("선호 수산물 TOP5")

                st.pyplot(fig1)
            else:
                st.info("📌 수산물 데이터가 없습니다.")
        except Exception as e:
            st.error(f"데이터 로드 오류 (수산물): {e}")
    else:
        st.error("⚠️ '선택한_수산물' 컬럼이 없습니다.")

    # 메뉴 TOP5
    st.markdown("### 🍽️ 메뉴 선호도 TOP5")
    menu_list = []
    if '선택한_메뉴' in df.columns:
        try:
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
                    palette=["#A7C7E7", "#89CFF0", "#7EC8E3", "#5DADE2", "#3498DB"]
                )
                ax2.set_title("선호 메뉴 TOP5", fontproperties=fontprop)
                ax2.set_xlabel("응답 수", fontproperties=fontprop)
                ax2.set_ylabel("메뉴", fontproperties=fontprop)
                for label in ax2.get_yticklabels():
                    label.set_fontproperties(fontprop)
                for label in ax2.get_xticklabels():
                    label.set_fontproperties(fontprop)

                st.pyplot(fig2)
            else:
                st.info("📌 메뉴 데이터가 없습니다.")
        except Exception as e:
            st.error(f"데이터 로드 오류 (메뉴): {e}")
    else:
        st.error("⚠️ '선택한_메뉴' 컬럼이 없습니다.")

    # 날짜별 응답 추이
    st.markdown("### ⏱️ 날짜별 응답 추이")
    if '설문일시' in df.columns:
        try:
            df['설문일자'] = pd.to_datetime(df['설문일시'], errors='coerce').dt.date
            daily_count = df.groupby('설문일자').size().reset_index(name='응답수')

            if not daily_count.empty:
                fig3, ax3 = plt.subplots()
                ax3.plot(daily_count['설문일자'], daily_count['응답수'], marker='o')
                ax3.set_ylabel("응답 수", fontproperties=fontprop)
                ax3.set_xlabel("날짜", fontproperties=fontprop)
                ax3.set_title("날짜별 응답 추이", fontproperties=fontprop)

                ax3.grid(True, linestyle="--", alpha=0.5)
                fig3.autofmt_xdate()
                st.pyplot(fig3)
            else:
                st.info("📌 날짜별 데이터가 없습니다.")
        except Exception as e:
            st.error(f"데이터 로드 오류 (날짜): {e}")


# -------------------------------------------------
# ✅ 시간/설정
# -------------------------------------------------
KST = timezone(timedelta(hours=9))
ADMIN_PASSWORD = "bluefood2025"

def get_korean_time():
    return datetime.now(KST)

def format_korean_time():
    return get_korean_time().strftime('%Y-%m-%d %H:%M:%S')


# -------------------------------------------------
# ✅ Google Sheets 연결 & 저장
# -------------------------------------------------
def get_google_sheet_cached():
    """Google Sheets 연결"""
    debug_container = st.empty()
    with debug_container.container():
        try:
            if "gcp_service_account" not in st.secrets:
                st.error("❌ [DEBUG] gcp_service_account 누락")
                return None
            if "google_sheets" not in st.secrets:
                st.error("❌ [DEBUG] google_sheets 설정 누락")
                return None

            creds_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in creds_dict:
                original_key = creds_dict["private_key"]
                if "\\n" in original_key:
                    creds_dict["private_key"] = original_key.replace("\\n", "\n")

            google_sheets_config = st.secrets["google_sheets"]
            sheet_name = google_sheets_config.get("google_sheet_name")
            sheet_id = google_sheets_config.get("google_sheet_id")

            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"
            ]

            try:
                creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            except Exception as auth_error:
                st.error(f"❌ [DEBUG] 서비스 계정 인증 실패: {auth_error}")
                st.code(traceback.format_exc())
                return None

            try:
                client = gspread.authorize(creds)
            except Exception:
                st.error("❌ [DEBUG] gspread 클라이언트 생성 실패")
                return None

            sheet = None
            if sheet_id:
                try:
                    workbook = client.open_by_key(sheet_id)
                    sheet = workbook.sheet1
                except Exception as e:
                    st.warning(f"⚠️ [DEBUG] Sheet ID로 열기 실패: {e}")

            if sheet is None and sheet_name:
                try:
                    workbook = client.open(sheet_name)
                    sheet = workbook.sheet1
                except Exception as e:
                    st.error(f"❌ [DEBUG] '{sheet_name}' 열기 실패: {e}")

            if sheet is None:
                st.error("❌ [DEBUG] 모든 방법으로 시트 열기 실패")
                return None

            try:
                setup_sheet_headers(sheet)
            except Exception as e:
                st.warning(f"⚠️ [DEBUG] 헤더 설정 중 오류: {e}")

            st.success("✅ [DEBUG] Google Sheets 연결 완료!")
            return sheet

        except gspread.exceptions.APIError as e:
            st.error(f"❌ [DEBUG] Google Sheets API 오류: {e}")
            return None
        except Exception as e:
            st.error(f"❌ [DEBUG] 예상치 못한 오류: {e}")
            st.error("🔍 오류 세부 정보:")
            st.code(traceback.format_exc())
            return None


def setup_sheet_headers(sheet):
    """시트에 헤더 없으면 생성"""
    try:
        first_row = sheet.row_values(1)
        if not first_row or all(cell == '' for cell in first_row):
            headers = ['이름', '식별번호', '설문일시', '선택한_수산물', '선택한_메뉴']
            sheet.append_row(headers)
        else:
            st.write("🟢 [DEBUG] 기존 헤더 사용")
    except Exception as e:
        st.warning(f"⚠️ [DEBUG] 헤더 설정 중 오류: {e}")
        st.code(traceback.format_exc())


def save_to_google_sheets(name, id_number, selected_ingredients, selected_menus):
    """Google Sheets에 응답 저장"""
    if st.session_state.get("already_saved", False):
        st.info("🟢 이미 저장된 데이터입니다.")
        return True
    
    try:
        st.info("🔄 Google Sheets에 데이터를 저장하는 중...")
        sheet = get_google_sheet_cached()
        if sheet is None:
            st.error("❌ Google Sheets 연결에 실패했습니다.")
            return False

        import json
        menus_text = json.dumps(selected_menus, ensure_ascii=False)
        ingredients_text = ', '.join(selected_ingredients)
        current_time = format_korean_time()

        row_data = [name, id_number, current_time, ingredients_text, menus_text]
        sheet.append_row(row_data, value_input_option="RAW")
        
        st.session_state.google_sheets_success = True
        st.session_state.already_saved = True
        
        st.success("✅ Google Sheets에 데이터가 성공적으로 저장되었습니다!")
        return True

    except gspread.exceptions.APIError as e:
        st.error(f"❌ Google API 오류: {e}")
        if "PERMISSION_DENIED" in str(e):
            st.error("💡 권한 문제: 서비스 계정에 시트 편집 권한이 필요합니다.")
        st.session_state.google_sheets_success = False
        return False
    except Exception as e:
        st.error(f"❌ Google Sheets 저장 중 오류 발생: {e}")
        st.session_state.google_sheets_success = False
        return False


def save_to_excel(name, id_number, selected_ingredients, selected_menus):
    """로컬 엑셀에도 백업 저장"""
    if st.session_state.get("already_saved", False):
        return "skipped", None

    # 시트 저장 시도 (성공/실패와 관계없이 계속 진행)
    save_to_google_sheets(name, id_number, selected_ingredients, selected_menus)
    
    try:
        new_data = {
            '이름': name,
            '식별번호': id_number,
            '설문일시': format_korean_time(),
            '선택한_수산물': ', '.join(selected_ingredients),
            '선택한_메뉴': ', '.join([f"{ingredient}: {', '.join(menus)}"
                                   for ingredient, menus in selected_menus.items()])
        }

        for ingredient in selected_ingredients:
            new_data[f'{ingredient}_메뉴'] = ', '.join(st.session_state.selected_menus.get(ingredient, []))

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


# -------------------------------------------------
# ✅ 전역 상태 기본값
# -------------------------------------------------
st.set_page_config(
    page_title="블루푸드 선호도 조사",
    page_icon="🐟",
    layout="wide" if not MOBILE_MODE else "centered"
)

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


# -------------------------------------------------
# ✅ 메뉴 데이터 / 카테고리 데이터
# -------------------------------------------------
MENU_DATA = {
    '맛살': {
        '밥/죽': ['게맛살볶음밥'],
        '무침': ['게맛살콩나물무침'],
        '볶음': ['맛살볶음'],
        '부침': ['맛살전']
    },
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
    '김': {
        '밥/죽': ['김밥'],
        '무침': ['김무침'],
        '튀김': ['김부각'],
        '구이': ['김자반']
    },
    '다시마': {
        '무침': ['다시마채무침'],
        '볶음': ['다시마채볶음'],
        '튀김': ['다시마튀각']
    },
    '매생이': {
        '면류': ['매생이칼국수'],
        '국/탕': ['매생이굴국'],
        '부침': ['매생이전']
    },
    '미역': {
        '밥/죽': ['미역국밥'],
        '국/탕': ['미역국'],
        '무침': ['미역초무침'],
        '볶음': ['미역줄기볶음']
    },
    '파래': {
        '무침': ['파래무침'],
        '볶음': ['파래볶음'],
        '부침': ['물파래전']
    },
    '톳': {
        '밥/죽': ['톳밥'],
        '무침': ['톳무침']
    },
    '꼴뚜기': {
        '조림': ['꼴뚜기조림'],
        '찜': ['꼴뚜기찜'],
        '무침': ['꼴뚜기젓무침'],
        '볶음': ['꼴뚜기볶음']
    },
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
    '가재': {
        '찜': ['가재찜'],
        '구이': ['가재구이']
    },
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
    '다슬기': {
        '면류': ['다슬기수제비'],
        '국/탕': ['다슬기된장국'],
        '무침': ['다슬기무침'],
        '부침': ['다슬기파전']
    },
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
    '재첩': {
        '국/탕': ['재첩국'],
        '무침': ['재첩무침'],
        '부침': ['재첩부추전']
    },
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
    '고등어': {
        '조림': ['고등어조림'],
        '구이': ['고등어구이']
    },
    '갈치': {
        '조림': ['갈치조림'],
        '구이': ['갈치구이']
    },
    '꽁치': {
        '국/탕': ['꽁치김치찌개'],
        '조림': ['꽁치조림'],
        '구이': ['꽁치구이']
    },
    '대구': {
        '국/탕': ['맑은대구탕', '대구매운탕'],
        '조림': ['대구조림'],
        '부침': ['대구전']
    },
    '멸치': {
        '밥/죽': ['멸치김밥'],
        '볶음': ['멸치볶음']
    },
    '명태': {
        '국/탕': ['황태미역국'],
        '조림': ['코다리조림'],
        '찜': ['명태찜'],
        '무침': ['북어채무침'],
        '구이': ['코다리구이']
    },
    '박대': {
        '조림': ['박대조림'],
        '구이': ['박대구이']
    },
    '뱅어': {
        '무침': ['뱅어포무침'],
        '튀김': ['뱅어포튀김']
    },
    '병어': {
        '조림': ['병어조림'],
        '구이': ['병어구이']
    },
    '삼치': {
        '조림': ['삼치조림'],
        '튀김': ['삼치튀김'],
        '구이': ['삼치구이']
    },
    '아귀': {
        '국/탕': ['아귀탕'],
        '찜': ['아귀찜']
    },
    '연어': {
        '밥/죽': ['연어덮밥'],
        '구이': ['연어구이'],
        '생식류/절임류/장류': ['연어회']
    },
    '임연수': {
        '조림': ['임연수조림'],
        '구이': ['임연수구이']
    },
    '장어': {
        '밥/죽': ['장어덮밥'],
        '조림': ['장어조림'],
        '찜': ['장어찜'],
        '튀김': ['장어튀김'],
        '구이': ['장어구이']
    },
    '조기': {
        '조림': ['조기조림'],
        '찜': ['조기찜'],
        '구이': ['조기구이']
    }
}


INGREDIENT_CATEGORIES = {
    '🍤 가공수산물': ['맛살', '어란', '어묵', '쥐포'],
    '🌿 해조류': ['김', '다시마', '매생이', '미역', '파래', '톳'],
    '🦑 연체류': ['꼴뚜기', '낙지', '문어', '오징어', '주꾸미'],
    '🦀 갑각류': ['가재', '게', '새우'],
    '🐚 패류': ['다슬기', '꼬막', '가리비', '골뱅이', '굴', '미더덕', '바지락', '백합', '소라', '재첩', '전복', '홍합'],
    '🐟 어류': ['가자미', '다랑어', '고등어', '갈치', '꽁치', '대구', '멸치', '명태', '박대', '뱅어', '병어', '삼치', '아귀', '연어', '임연수', '장어', '조기']
}


# -------------------------------------------------
# ✅ 참여자 화이트리스트
# -------------------------------------------------
@st.cache_data(ttl=300)
def load_allowed_name_id_pairs():
    """
    st.secrets 또는 구글시트 '참여자_명단' 워크시트로부터
    (이름, 식별번호) 허용 쌍 집합을 만든다.
    """
    pairs = set()

    # 1) st.secrets 기반 허용 목록
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

    # 2) 구글시트 참여자_명단 시트
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


# -------------------------------------------------
# ✅ 화면 단계별 UI
# -------------------------------------------------

def show_info_form():
    # 맨 위로 스크롤
    st.markdown(
        """
        <script>
        setTimeout(function() {
            window.scrollTo({top: 0, behavior: 'smooth'});
        }, 100);
        </script>
        """,
        unsafe_allow_html=True
    )

    st.subheader("📝 참여자 정보 입력")

    # 입력 폼 스타일을 모바일 기준으로 조금만(너무 큰 폰트 X)
    st.markdown(
        """
        <style>
        div.row-widget.stTextInput label {
            font-size: 20px !important;
            font-weight: bold !important;
            color: #222 !important;
        }
        div.row-widget.stTextInput input {
            font-size: 20px !important;
            height: 48px !important;
        }
        div.stButton > button {
            font-size: 20px !important;
            font-weight: bold !important;
            height: 50px !important;
            border-radius: 10px !important;
            background: linear-gradient(135deg, #4facfe, #00f2fe);
            color: white !important;
        }
        div.stButton > button:hover {
            background: linear-gradient(135deg, #00b4d8, #0096c7);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    with st.form("info_form"):
        # 모바일은 1열이 더 안정적이라 2열 -> 1열 전환
        name = st.text_input("성함", placeholder="홍길동", max_chars=20)
        id_number = st.text_input("식별번호", placeholder="예: HG001", max_chars=20)

        submitted = st.form_submit_button("설문 시작하기", use_container_width=True)

        if submitted:
            if name and id_number:
                if not is_valid_name_id(name, id_number):
                    st.error("❌ 등록되지 않은 성함/식별번호입니다. 담당자로부터 받은 올바른 정보를 입력해주세요.")
                    return

                st.session_state.name = name
                st.session_state.id_number = id_number
                st.session_state.step = 'ingredients'

                st.markdown(
                    """
                    <script>
                    setTimeout(function() {
                        window.scrollTo({top: 0, behavior: 'smooth'});
                    }, 200);
                    </script>
                    """,
                    unsafe_allow_html=True
                )
                st.rerun()
            else:
                st.error("성함과 식별번호를 모두 입력해주세요.")


def show_ingredient_selection_mobile():
    """
    모바일용 수산물 선택 화면
    - 이미지 / 큰 카드 제거
    - 3열 칩 형태로 배치
    - 카테고리별 expander
    - 최소 3개~최대 9개
    """
    st.markdown(
        """
        <script>
        setTimeout(function() {
            window.scrollTo({top: 0, behavior: 'smooth'});
        }, 100);
        </script>
        """,
        unsafe_allow_html=True
    )

    st.subheader("🐟 선호 수산물 선택")
    st.caption("최소 3개, 최대 9개까지 선택해주세요.")

    # 칩 스타일 (compact)
    st.markdown("""
    <style>
    .chip-box {
        border: 2px solid #0096c7;
        border-radius: 10px;
        padding: 6px 8px;
        font-size: 16px;
        font-weight: 600;
        line-height: 1.2;
        text-align: center;
        margin-bottom: 6px;
        width: 100%;
        min-height: 44px;
        display:flex;
        align-items:center;
        justify-content:center;
    }
    .chip-unselected {
        border-color: #ccc;
        color: #000;
        background: #fff;
    }
    .chip-selected {
        border-color: #0096c7;
        background: #00b4d8;
        color: #fff;
    }
    </style>
    """, unsafe_allow_html=True)

    # 현재 몇 개 선택 중인지 안내
    cnt = len(st.session_state.selected_ingredients)
    if 3 <= cnt <= 9:
        st.success(f"현재 {cnt}개 선택됨")
    elif cnt < 3:
        st.warning(f"{cnt}개 선택됨 (최소 3개 필요)")
    else:
        st.error(f"{cnt}개 선택됨 (최대 9개까지)")

    # 카테고리별로 보여주기
    for category, ing_list in INGREDIENT_CATEGORIES.items():
        with st.expander(category, expanded=True):
            cols = st.columns(3)
            for i, ing in enumerate(ing_list):
                with cols[i % 3]:
                    selected_now = ing in st.session_state.selected_ingredients

                    # 칩 시각화
                    st.markdown(
                        f"""
                        <div class="chip-box {'chip-selected' if selected_now else 'chip-unselected'}">
                            {ing}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    # 실제 선택 위젯
                    new_val = st.checkbox(
                        "선택",
                        value=selected_now,
                        key=f"ing_{ing}"
                    )

                    # 상태 업데이트
                    if new_val and (ing not in st.session_state.selected_ingredients):
                        if len(st.session_state.selected_ingredients) < 9:
                            st.session_state.selected_ingredients.append(ing)
                        else:
                            st.error("최대 9개까지만 선택할 수 있습니다.")
                    if (not new_val) and (ing in st.session_state.selected_ingredients):
                        st.session_state.selected_ingredients.remove(ing)

    st.markdown("---")

    # 다음 단계 버튼
    can_go_next = (3 <= len(st.session_state.selected_ingredients) <= 9)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("전체 해제", use_container_width=True):
            st.session_state.selected_ingredients = []
            st.session_state.selected_menus = {}
            st.experimental_rerun()

    with col_b:
        if st.button("다음 단계 →", disabled=not can_go_next, use_container_width=True, type="primary"):
            # 다음 단계에서 사용할 dict 준비
            st.session_state.selected_menus = {
                ing: st.session_state.selected_menus.get(ing, [])
                for ing in st.session_state.selected_ingredients
            }
            st.session_state.step = 'menus'

            st.markdown(
                """
                <script>
                setTimeout(function() {
                    window.scrollTo({top: 0, behavior: 'smooth'});
                }, 200);
                </script>
                """,
                unsafe_allow_html=True
            )
            st.rerun()


def show_menu_selection_mobile():
    """
    모바일용 메뉴 선택 화면
    - 수산물별 expander (아코디언 구조)
    - 각 메뉴를 2열 칩으로 배치
    - 각 수산물마다 최소 1개 이상
    """
    st.markdown(
        """
        <script>
        setTimeout(function() {
            window.scrollTo({top: 0, behavior: 'smooth'});
        }, 100);
        </script>
        """,
        unsafe_allow_html=True
    )

    st.subheader("🍽️ 선호 메뉴 선택")
    st.caption("각 수산물마다 최소 1개 이상의 선호 메뉴를 골라주세요.")

    all_valid = True

    for ing in st.session_state.selected_ingredients:
        with st.expander(f"🐟 {ing} 요리 선택", expanded=False):
            menus_flat = []
            if ing in MENU_DATA:
                for menu_list in MENU_DATA[ing].values():
                    menus_flat.extend(menu_list)

            # 2열로 촘촘하게
            cols = st.columns(2)
            for i, menu_name in enumerate(menus_flat):
                with cols[i % 2]:
                    already = menu_name in st.session_state.selected_menus.get(ing, [])

                    st.markdown(
                        f"""
                        <div style="
                            border:2px solid {'#0096c7' if already else '#ccc'};
                            border-radius:10px;
                            padding:6px;
                            font-size:16px;
                            font-weight:600;
                            line-height:1.3;
                            margin-bottom:6px;
                            background:{'#00b4d8' if already else '#fff'};
                            color:{'#fff' if already else '#000'};
                            text-align:center;
                            min-height:44px;
                            display:flex;
                            align-items:center;
                            justify-content:center;
                        ">
                            {menu_name}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    checked = st.checkbox(
                        "선택",
                        value=already,
                        key=f"menu_{ing}_{menu_name}"
                    )

                    if checked and menu_name not in st.session_state.selected_menus[ing]:
                        st.session_state.selected_menus[ing].append(menu_name)
                    if (not checked) and (menu_name in st.session_state.selected_menus[ing]):
                        st.session_state.selected_menus[ing].remove(menu_name)

            # 이 재료 최소 1개 선택했는지 검사
            if len(st.session_state.selected_menus.get(ing, [])) == 0:
                all_valid = False
                st.warning(f"{ing}: 최소 1개 선택 필요")
            else:
                st.success(f"{ing}: {len(st.session_state.selected_menus[ing])}개 선택됨")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← 이전 단계", use_container_width=True):
            st.session_state.step = 'ingredients'
            st.rerun()

    with col2:
        if st.button("설문 완료하기", disabled=not all_valid, use_container_width=True, type="primary"):
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
    st.markdown(
        """
        <script>
        setTimeout(function() {
            window.scrollTo({top: 0, behavior: 'smooth'});
        }, 100);
        </script>
        """,
        unsafe_allow_html=True
    )

    st.balloons()
    st.success("🎉 설문이 완료되었습니다! 참여해주셔서 감사합니다.")

    if hasattr(st.session_state, 'google_sheets_success') and st.session_state.google_sheets_success:
        st.success("✅ 데이터가 Google Sheets에 성공적으로 저장되었습니다!")
    else:
        st.warning("⚠️ Google Sheets 연결에 문제가 있어 로컬 백업 파일에 저장되었습니다.")

    with st.expander("📊 설문 결과 요약", expanded=True):
        st.markdown(f"**참여자:** {st.session_state.name}")
        st.markdown(f"**식별번호:** {st.session_state.id_number}")
        st.markdown(f"**설문 완료 시간:** {format_korean_time()}")

        st.markdown("### 선택하신 수산물")
        ing_text = " | ".join(st.session_state.selected_ingredients)
        st.markdown(f"🏷️ {ing_text}")

        st.markdown("### 선호하시는 메뉴")
        for ing, menus in st.session_state.selected_menus.items():
            if menus:
                menu_text = ", ".join(menus)
                st.markdown(f"**{ing}:** {menu_text}")

    # 관리자만 다운로드 버튼
    if st.session_state.is_admin and 'filename' in st.session_state and st.session_state.filename:
        st.markdown("---")
        st.markdown("### 🔐 관리자 전용")
        if os.path.exists(st.session_state.filename):
            with open(st.session_state.filename, 'rb') as file:
                st.download_button(
                    label="📥 백업 파일 다운로드",
                    data=file.read(),
                    file_name=f"bluefood_survey_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    type="primary",
                    use_container_width=True
                )

    # 새 설문 다시 시작
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


# -------------------------------------------------
# ✅ main(): 모바일일 땐 사이드바 대신 상단 안내만
# -------------------------------------------------
def main():
    # 화면 강제로 맨 위
    st.markdown(
        """
        <script>
        setTimeout(function() { window.scrollTo(0, 0); }, 100);
        </script>
        """,
        unsafe_allow_html=True
    )

    if MOBILE_MODE:
        # 모바일에서는 사이드바를 쓰지 않고
        # 상단에 안내/진행상황을 접어서(expander) 보여준다.
        with st.expander("📋 설문 안내 / 진행 상황 열기"):
            st.markdown(
                """
                **연구명**  
                요양원 거주 고령자 대상 건강 상태 및 블루푸드 식이 DB 구축

                **담당자**  
                류혜리, 유정연 (서울대학교 농생명공학부 박사과정)

                **진행 단계**  
                1) 정보입력 →  
                2) 수산물 선택 →  
                3) 메뉴 선택 →  
                4) 완료

                **개인정보 보호**  
                연구 목적 이외 사용하지 않습니다.
                """,
                unsafe_allow_html=False
            )

            # 진행 상황 바
            if st.session_state.step == 'info':
                st.progress(0.25, "1단계: 정보 입력")
            elif st.session_state.step == 'ingredients':
                st.progress(0.5, "2단계: 수산물 선택")
            elif st.session_state.step == 'menus':
                st.progress(0.75, "3단계: 메뉴 선택")
            elif st.session_state.step == 'complete':
                st.progress(1.0, "✅ 설문 완료!")

        # 관리자 로그인/관리 도구는 따로 추가(선택)
        if st.session_state.is_admin:
            with st.expander("🔐 관리자 영역"):
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
                    except:
                        st.markdown("**📊 데이터 로드 오류**")
                else:
                    st.info("아직 설문 데이터가 없습니다.")

                if st.button("🚪 로그아웃"):
                    st.session_state.is_admin = False
                    st.session_state.show_admin_login = False
                    st.rerun()
        else:
            # 관리자가 아닐 때만: 로그인 버튼
            with st.expander("관리자 로그인"):
                if not st.session_state.is_admin:
                    password = st.text_input("관리자 패스워드", type="password")
                    if st.button("로그인"):
                        if password == ADMIN_PASSWORD:
                            st.session_state.is_admin = True
                            st.session_state.show_admin_login = False
                            st.success("관리자로 로그인되었습니다!")
                            st.rerun()
                        else:
                            st.error("잘못된 패스워드입니다.")

    else:
        # 데스크탑 모드라면 기존 사이드바 레이아웃을 그대로 유지하고 싶은 경우
        # (원본 코드의 sidebar 내용을 그대로 넣으면 됨)
        with st.sidebar:
            st.markdown(
                """
                <div style="
                    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                    padding: 20px;
                    border-radius: 15px;
                    margin-bottom: 20px;
                    color: white;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.15);
                ">
                    <h3 style="text-align:center; margin-bottom:10px;">📌 연구 정보</h3>
                    <div style="background: rgba(255,255,255,0.15); padding:10px; border-radius:10px; margin-bottom:10px;">
                        <strong>🔹 연구명</strong><br>
                        요양원 거주 고령자 대상 건강 상태 및<br>블루푸드 식이 데이터베이스 구축
                    </div>
                    <div style="background: rgba(255,255,255,0.15); padding:10px; border-radius:10px; margin-bottom:10px;">
                        <strong>🔹 정부과제명</strong><br>
                        글로벌 블루푸드 미래리더 양성 프로젝트
                    </div>
                    <div style="background: rgba(255,255,255,0.15); padding:10px; border-radius:10px;">
                        <strong>🔹 연구 담당자</strong><br>
                        류혜리, 유정연<br>(서울대학교 농생명공학부 박사과정)
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            # 관리자 / 다운로드 등등은 데스크탑에서 원래 하던 대로...

    # 메인 타이틀
    st.title("🐟 블루푸드 선호도 조사")

    # 단계별 화면 호출
    if st.session_state.step == 'info':
        show_info_form()
    elif st.session_state.step == 'ingredients':
        show_ingredient_selection_mobile()
    elif st.session_state.step == 'menus':
        show_menu_selection_mobile()
    elif st.session_state.step == 'complete':
        show_completion()


# -------------------------------------------------
# ✅ 엔트리 포인트
# -------------------------------------------------
if __name__ == "__main__":
    main()
