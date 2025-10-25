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

# ====== 전역 라이트 모드 강제 CSS ======
LIGHT_FORCE_CSS = """
<style>
/* 전체 배경을 흰색으로 강제 */
html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"],
[data-testid="stSidebar"], [data-testid="stSidebarContent"],
[data-testid="stMain"], .main, .block-container {
    background-color: #ffffff !important;
    color: #000000 !important;
}

/* 기본 텍스트도 검정 계열로 */
* {
    color: #000000 !important;
    box-sizing: border-box;
}

/* 상태 요약 박스 */
.status-banner {
    background-color: #e9f4ff !important;
    color: #003049 !important;
    border-radius: 8px;
    border: 1px solid #a3c8ff;
    padding: 12px 16px;
    font-size: 16px;
    font-weight: 500;
    margin-bottom: 16px;
}

/* 탭 스트립(카테고리 라인) - 참고용 (현재 st.tabs() 자체 UI는 따로 렌더) */
.tab-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 12px;
    border-bottom: 2px solid #dcdcdc;
    padding: 8px 0 12px 0;
    margin-bottom: 12px;
    font-size: 16px;
    font-weight: 600;
}
.tab-item {
    display: flex;
    align-items: center;
    gap: 4px;
    padding-bottom: 4px;
    border-bottom: 3px solid transparent;
}
.tab-item.active {
    color: #c1121f !important;
    border-bottom-color: #c1121f;
}
.tab-emoji {
    font-size: 18px;
}

/* 식재료 카드 박스 디자인 (기본/선택) */
.card-box {
    border: 2px solid #666666 !important;
    background-color: #ffffff !important;
    color: #000000 !important;
    border-radius:10px;
    padding:12px 8px;
    margin-bottom:6px;
    min-height:60px;
    display:flex;
    align-items:center;
    justify-content:center;
    text-align:center;
}
.card-box.selected {
    background-color: #00b4d8 !important;
    border-color: #0096c7 !important;
    color: #ffffff !important;
}
.card-label {
    width: 100%;
    text-align: center;
    font-size:16px;
    font-weight:600;
    line-height:1.3;
    word-break: keep-all;
}

/* 메뉴 카드와 비슷하게 쓰일 수 있는 공용 스타일(흰 배경) */
.menu-card-box {
    border: 2px solid #666666 !important;
    background-color: #ffffff !important;
    color: #000000 !important;
    border-radius:10px;
    padding:12px 8px;
    margin-bottom:6px;
    min-height:60px;
    display:flex;
    align-items:center;
    justify-content:center;
    text-align:center;
    font-size:16px;
    font-weight:600;
}
.menu-card-box.selected {
    background-color:#00b4d8 !important;
    border-color:#0096c7 !important;
    color:#ffffff !important;
}

/* 경고/성공 메시지 가독성도 라이트 기준으로 */
div[role="alert"] {
    color: #000000 !important;
}

/* 사이드바 카드들 배경 흰색 유지 */
.sidebar-card {
    background: #ffffff !important;
    border: 1px solid #ddd !important;
    box-shadow: 0 4px 10px rgba(0,0,0,0.1) !important;
    border-radius: 15px !important;
    padding: 20px !important;
    margin-bottom: 20px !important;
    font-size: 17px !important;
    line-height: 1.6 !important;
    color: #333 !important;
}

/* 진행상황 progressbar 텍스트가 안보이는 문제를 줄이기 */
[data-testid="stProgressBar"] div div {
    color:#000000 !important;
}

/* 버튼 폰트 커지게 (모바일 터치 편하게) */
div.stButton > button {
    font-size: 20px !important;
    font-weight: bold !important;
    height: 48px !important;
    border-radius: 10px !important;
}
</style>
"""

# ====== NanumGothic 폰트 설정 (선택사항: 기존 코드 유지) ======
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

# ===== 관리자 대시보드 (필요시 유지) =====
def show_admin_dashboard(df):
    st.markdown("## 📊 관리자 대시보드")

    if df is None or df.empty:
        st.warning("⚠️ 응답 데이터가 없습니다.")
        return

    st.markdown(f"**총 응답자 수:** {df['식별번호'].nunique()}명")
    st.markdown(f"**총 응답 수:** {len(df)}건")
    st.markdown(f"**최근 응답 시간:** {df['설문일시'].max()}")

    dup = df[df.duplicated('식별번호', keep=False)]
    st.markdown("### 🔍 중복 응답 감지")
    if not dup.empty:
        st.warning(f"⚠️ {dup['식별번호'].nunique()}명의 중복 응답 발견")
        st.dataframe(dup)
    else:
        st.success("✅ 중복 응답 없음")

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

                if fontprop:
                    ax1.set_title("선호 수산물 TOP5", fontproperties=fontprop)
                    ax1.set_xlabel("응답 수", fontproperties=fontprop)
                    ax1.set_ylabel("수산물", fontproperties=fontprop)
                    for label in ax1.get_yticklabels():
                        label.set_fontproperties(fontprop)
                    for label in ax1.get_xticklabels():
                        label.set_fontproperties(fontprop)
                else:
                    ax1.set_title("선호 수산물 TOP5")

                st.pyplot(fig1)
            else:
                st.info("📌 수산물 데이터가 없습니다.")
        except Exception as e:
            st.error(f"데이터 로드 오류 (수산물): {e}")
    else:
        st.error("⚠️ '선택한_수산물' 컬럼이 없습니다.")

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
                if fontprop:
                    ax2.set_title("선호 메뉴 TOP5", fontproperties=fontprop)
                    ax2.set_xlabel("응답 수", fontproperties=fontprop)
                    ax2.set_ylabel("메뉴", fontproperties=fontprop)
                    for label in ax2.get_yticklabels():
                        label.set_fontproperties(fontprop)
                    for label in ax2.get_xticklabels():
                        label.set_fontproperties(fontprop)
                else:
                    ax2.set_title("선호 메뉴 TOP5")

                st.pyplot(fig2)
            else:
                st.info("📌 메뉴 데이터가 없습니다.")
        except Exception as e:
            st.error(f"데이터 로드 오류 (메뉴): {e}")
    else:
        st.error("⚠️ '선택한_메뉴' 컬럼이 없습니다.")

    st.markdown("### ⏱️ 날짜별 응답 추이")
    if '설문일시' in df.columns:
        try:
            df['설문일자'] = pd.to_datetime(df['설문일시'], errors='coerce').dt.date
            daily_count = df.groupby('설문일자').size().reset_index(name='응답수')

            if not daily_count.empty:
                fig3, ax3 = plt.subplots()
                ax3.plot(daily_count['설문일자'], daily_count['응답수'], marker='o')
                ax3.set_ylabel("응답 수")
                ax3.set_xlabel("날짜")
                if fontprop:
                    ax3.set_title("날짜별 응답 추이", fontproperties=fontprop)
                    ax3.set_xlabel("날짜", fontproperties=fontprop)
                    ax3.set_ylabel("응답 수", fontproperties=fontprop)
                else:
                    ax3.set_title("날짜별 응답 추이")

                ax3.grid(True, linestyle="--", alpha=0.5)
                fig3.autofmt_xdate()
                st.pyplot(fig3)
            else:
                st.info("📌 날짜별 데이터가 없습니다.")
        except Exception as e:
            st.error(f"데이터 로드 오류 (날짜): {e}")


# ===== 시간대 / 현재시각 =====
KST = timezone(timedelta(hours=9))
ADMIN_PASSWORD = "bluefood2025"

def get_korean_time():
    return datetime.now(KST)

def format_korean_time():
    return get_korean_time().strftime('%Y-%m-%d %H:%M:%S')

# ===== Google Sheets 연결 =====
def get_google_sheet_cached():
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
    if st.session_state.get("already_saved", False):
        return "skipped", None
        
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


# ===== 세션 기본값 =====
st.set_page_config(
    page_title="블루푸드 선호도 조사",
    page_icon="🐟",
    layout="centered"  # 모바일 최적
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

# ===== 데이터 사전 =====
MENU_DATA = {
    '맛살': {'밥/죽': ['게맛살볶음밥'],
           '무침': ['게맛살콩나물무침'],
           '볶음': ['맛살볶음'],
           '부침': ['맛살전']},
    '어란': {'밥/죽': ['날치알밥'],
           '면류': ['명란파스타'],
           '국/탕': ['알탕'],
           '찜': ['날치알달걀찜'],
           '무침': ['명란젓갈'],
           '볶음': ['날치알스크램블에그'],
           '부침': ['날치알계란말이'],
           '구이': ['명란구이']},
    '어묵': {'밥/죽': ['어묵볶음밥'],
           '면류': ['어묵우동'],
           '국/탕': ['어묵탕'],
           '조림': ['어묵조림'],
           '찜': ['콩나물어묵찜', '어묵찜'],
           '볶음': ['매콤어묵볶음', '간장어묵볶음'],
           '부침': ['어묵전'],
           '튀김': ['어묵고로케']},
    '쥐포': {'조림': ['쥐포조림'],
           '무침': ['쥐포무침'],
           '볶음': ['쥐포볶음'],
           '부침': ['쥐포전'],
           '튀김': ['쥐포튀김'],
           '구이': ['쥐포구이']},
    '김': {'밥/죽': ['김밥'],
         '무침': ['김무침'],
         '튀김': ['김부각'],
         '구이': ['김자반']},
    '다시마': {'무침': ['다시마채무침'],
           '볶음': ['다시마채볶음'],
           '튀김': ['다시마튀각']},
    '매생이': {'면류': ['매생이칼국수'],
            '국/탕': ['매생이굴국'],
            '부침': ['매생이전']},
    '미역': {'밥/죽': ['미역국밥'],
           '국/탕': ['미역국'],
           '무침': ['미역초무침'],
           '볶음': ['미역줄기볶음']},
    '파래': {'무침': ['파래무침'],
           '볶음': ['파래볶음'],
           '부침': ['물파래전']},
    '톳': {'밥/죽': ['톳밥'],
         '무침': ['톳무침']},
    '꼴뚜기': {'조림': ['꼴뚜기조림'],
            '찜': ['꼴뚜기찜'],
            '무침': ['꼴뚜기젓무침'],
            '볶음': ['꼴뚜기볶음']},
    '낙지': {'밥/죽': ['낙지비빔밥'],
           '면류': ['낙지수제비'],
           '국/탕': ['낙지연포탕'],
           '찜': ['낙지찜'],
           '무침': ['낙지초무침'],
           '볶음': ['낙지볶음'],
           '구이': ['낙지호롱구이'],
           '기타(생식)': ['낙지탕탕이']},
    '문어': {'밥/죽': ['문어볶음밥'],
           '면류': ['문어라면'],
           '국/탕': ['문어탕'],
           '조림': ['문어조림'],
           '찜': ['문어콩나물찜'],
           '무침': ['문어초무침'],
           '볶음': ['문어볶음'],
           '부침': ['문어전'],
           '튀김': ['문어튀김'],
           '기타(생식)': ['문어회']},
    '오징어': {'밥/죽': ['오징어덮밥'],
            '국/탕': ['오징어무국'],
            '조림': ['오징어조림'],
            '찜': ['오징어콩나물찜', '오징어숙회'],
            '무침': ['오징어초무침'],
            '볶음': ['오징어볶음'],
            '부침': ['오징어해물전'],
            '튀김': ['오징어튀김'],
            '구이': ['오징어버터구이'],
            '기타(생식)': ['오징어회']},
    '주꾸미': {'밥/죽': ['주꾸미볶음덮밥'],
            '면류': ['주꾸미감자수제비', '주꾸미짬뽕'],
            '국/탕': ['주꾸미연포탕'],
            '찜': ['주꾸미숙회', '주꾸미찜'],
            '무침': ['주꾸미무침'],
            '볶음': ['주꾸미볶음']},
    '가재': {'찜': ['가재찜'],
          '구이': ['가재구이']},
    '게': {'밥/죽': ['게살볶음밥'],
         '면류': ['게살파스타', '꽃게라면'],
         '국/탕': ['꽃게탕'],
         '조림': ['꽃게조림'],
         '찜': ['꽃게찜'],
         '무침': ['꽃게무침'],
         '볶음': ['꽃게볶음'],
         '튀김': ['꽃게강정'],
         '기타(생식)': ['간장게장', '양념게장']},
    '새우': {'밥/죽': ['새우볶음밥'],
          '면류': ['새우크림파스타'],
          '국/탕': ['새우달걀국', '얼큰새우매운탕'],
          '조림': ['새우조림'],
          '찜': ['새우달걀찜'],
          '무침': ['새우젓'],
          '볶음': ['건새우볶음'],
          '부침': ['새우전'],
          '튀김': ['새우튀김'],
          '구이': ['새우버터구이'],
          '기타(생식)': ['간장새우장', '양념새우장']},
    '다슬기': {'면류': ['다슬기수제비'],
            '국/탕': ['다슬기된장국'],
            '무침': ['다슬기무침'],
            '부침': ['다슬기파전']},
    '꼬막': {'밥/죽': ['꼬막비빔밥'],
           '면류': ['꼬막칼국수'],
           '국/탕': ['꼬막된장찌개'],
           '찜': ['꼬막찜'],
           '무침': ['꼬막무침'],
           '부침': ['꼬막전'],
           '구이': ['꼬막떡꼬치구이']},
    '가리비': {'밥/죽': ['가리비초밥'],
            '면류': ['가리비칼국수'],
            '국/탕': ['가리비탕'],
            '찜': ['가리비찜'],
            '무침': ['가리비초무침'],
            '볶음': ['가리비볶음'],
            '구이': ['가리비버터구이']},
    '골뱅이': {'밥/죽': ['골뱅이죽'],
            '면류': ['골뱅이비빔면'],
            '국/탕': ['골뱅이탕'],
            '무침': ['골뱅이무침'],
            '볶음': ['골뱅이볶음'],
            '튀김': ['골뱅이튀김'],
            '구이': ['골뱅이꼬치구이'],
            '기타(생식)': ['골뱅이물회']},
    '굴': {'밥/죽': ['굴국밥'],
         '면류': ['굴칼국수', '굴짬뽕'],
         '국/탕': ['매생이굴국', '굴순두부찌개'],
         '조림': ['굴조림'],
         '찜': ['굴찜'],
         '무침': ['굴무침'],
         '볶음': ['굴볶음'],
         '부침': ['굴전'],
         '튀김': ['굴튀김'],
         '구이': ['굴구이'],
         '기타(생식)': ['생굴']},
    '미더덕': {'밥/죽': ['미더덕밥'],
            '국/탕': ['미더덕된장찌개', '미더덕순두부찌개'],
            '찜': ['미더덕콩나물찜']},
    '바지락': {'밥/죽': ['바지락비빔밥'],
            '면류': ['바지락칼국수'],
            '국/탕': ['바지락미역국', '바지락순두부찌개'],
            '찜': ['바지락찜'],
            '무침': ['바지락무침'],
            '볶음': ['바지락볶음', '매콤바지락볶음'],
            '부침': ['바지락부추전']},
    '백합': {'밥/죽': ['백합볶음밥'],
           '면류': ['백합칼국수'],
           '국/탕': ['백합탕'],
           '찜': ['백합찜'],
           '무침': ['백합무침'],
           '볶음': ['백합볶음'],
           '구이': ['백합구이']},
    '소라': {'밥/죽': ['참소라야채죽'],
           '면류': ['소라비빔면'],
           '국/탕': ['소라된장찌개'],
           '조림': ['참소라장조림'],
           '찜': ['소라숙회'],
           '무침': ['소라무침'],
           '볶음': ['소라버터볶음'],
           '튀김': ['소라튀김'],
           '구이': ['소라구이'],
           '기타(생식)': ['소라회']},
    '재첩': {'국/탕': ['재첩국'],
           '무침': ['재첩무침'],
           '부침': ['재첩부추전']},
    '전복': {'밥/죽': ['전복죽'],
           '면류': ['전복파스타'],
           '국/탕': ['전복미역국'],
           '조림': ['전복장조림'],
           '찜': ['전복찜'],
           '무침': ['전복무침'],
           '볶음': ['전복볶음'],
           '구이': ['전복구이'],
           '기타(생식)': ['전복회']},
    '홍합': {'밥/죽': ['홍합죽'],
           '면류': ['홍합칼국수', '홍합짬뽕'],
           '국/탕': ['홍합탕', '홍합된장찌개'],
           '조림': ['홍합조림'],
           '찜': ['홍합찜'],
           '무침': ['홍합무침'],
           '볶음': ['홍합볶음'],
           '부침': ['홍합전'],
           '구이': ['홍합구이']},
    '가자미': {'국/탕': ['가자미미역국'],
            '조림': ['가자미조림'],
            '찜': ['가자미찜'],
            '부침': ['가자미전'],
            '튀김': ['가자미튀김'],
            '구이': ['가자미구이']},
    '다랑어': {'밥/죽': ['참치김밥'],
            '국/탕': ['참치김치찌개'],
            '볶음': ['참치양배추볶음'],
            '부침': ['참치달걀말이'],
            '구이': ['참치스테이크'],
            '생식류/절임류/장류': ['참치회']},
    '고등어': {'조림': ['고등어조림'],
            '구이': ['고등어구이']},
    '갈치': {'조림': ['갈치조림'],
           '구이': ['갈치구이']},
    '꽁치': {'국/탕': ['꽁치김치찌개'],
           '조림': ['꽁치조림'],
           '구이': ['꽁치구이']},
    '대구': {'국/탕': ['맑은대구탕', '대구매운탕'],
          '조림': ['대구조림'],
          '부침': ['대구전']},
    '멸치': {'밥/죽': ['멸치김밥'],
           '볶음': ['멸치볶음']},
    '명태': {'국/탕': ['황태미역국'],
           '조림': ['코다리조림'],
           '찜': ['명태찜'],
           '무침': ['북어채무침'],
           '구이': ['코다리구이']},
    '박대': {'조림': ['박대조림'],
           '구이': ['박대구이']},
    '뱅어': {'무침': ['뱅어포무침'],
           '튀김': ['뱅어포튀김']},
    '병어': {'조림': ['병어조림'],
           '구이': ['병어구이']},
    '삼치': {'조림': ['삼치조림'],
           '튀김': ['삼치튀김'],
           '구이': ['삼치구이']},
    '아귀': {'국/탕': ['아귀탕'],
           '찜': ['아귀찜']},
    '연어': {'밥/죽': ['연어덮밥'],
           '구이': ['연어구이'],
           '생식류/절임류/장류': ['연어회']},
    '임연수': {'조림': ['임연수조림'],
            '구이': ['임연수구이']},
    '장어': {'밥/죽': ['장어덮밥'],
           '조림': ['장어조림'],
           '찜': ['장어찜'],
           '튀김': ['장어튀김'],
           '구이': ['장어구이']},
    '조기': {'조림': ['조기조림'],
          '찜': ['조기찜'],
          '구이': ['조기구이']}
}

INGREDIENT_CATEGORIES = {
    '🍤 가공수산물': ['맛살', '어란', '어묵', '쥐포'],
    '🌿 해조류': ['김', '다시마', '매생이', '미역', '파래', '톳'],
    '🦑 연체류': ['꼴뚜기', '낙지', '문어', '오징어', '주꾸미'],
    '🦀 갑각류': ['가재', '게', '새우'],
    '🐚 패류': ['다슬기', '꼬막', '가리비', '골뱅이', '굴', '미더덕', '바지락', '백합', '소라', '재첩', '전복', '홍합'],
    '🐟 어류': ['가자미', '다랑어', '고등어', '갈치', '꽁치', '대구', '멸치', '명태', '박대', '뱅어', '병어', '삼치', '아귀', '연어', '임연수', '장어', '조기']
}

# ===== 참가자 화이트리스트 확인 =====
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
    return (name.strip(), id_number.strip().upper()) in allowed


# ===== UI 단계 함수들 =====

def show_info_form():
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

    # 입력폼(모바일 크게)
    st.markdown(
        """
        <style>
        div.row-widget.stTextInput label {
            font-size: 20px !important;
            font-weight: bold !important;
            color: #000 !important;
        }
        div.row-widget.stTextInput input {
            font-size: 20px !important;
            height: 50px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    with st.form("info_form"):
        name = st.text_input("성함", placeholder="홍길동", max_chars=20)
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


# ---- 한 재료 카드 (3열 그리드용) ----
def ingredient_card_block(ingredient_name: str, is_selected: bool, checkbox_key: str):
    card_class = "card-box selected" if is_selected else "card-box"

    st.markdown(
        f"""
        <div class="{card_class}">
            <div class="card-label">{ingredient_name}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    new_val = st.checkbox(
        "선택",
        value=is_selected,
        key=checkbox_key
    )
    return new_val


# ---- 식재료 선택 단계 ----
def show_ingredient_selection():
    st.subheader("🐟 수산물 원재료 선호도")
    st.markdown("최소 3개 이상, 최대 9개까지 선택해주세요.")

    # 현재 선택 개수 요약
    selected_count = len(st.session_state.selected_ingredients)
    if selected_count < 3:
        status_msg = f"현재 {selected_count}개 선택됨 · 최소 3개 이상 선택해주세요"
    elif selected_count > 9:
        status_msg = f"현재 {selected_count}개 선택됨 · 최대 9개까지만 가능합니다"
    else:
        status_msg = f"현재 {selected_count}개 선택됨"

    st.markdown(
        f"""
        <div class="status-banner">{status_msg}</div>
        """,
        unsafe_allow_html=True
    )

    # 카테고리 탭
    category_names = list(INGREDIENT_CATEGORIES.keys())
    tabs = st.tabs(category_names)

    for tab, category in zip(tabs, category_names):
        with tab:
            st.markdown(
                f"""
                <h3 style="margin-top:8px; margin-bottom:12px; font-size:20px; font-weight:700;">
                    {category}
                </h3>
                """,
                unsafe_allow_html=True
            )

            ingredients = INGREDIENT_CATEGORIES[category]

            # 3열 그리드로 렌더
            for row_start in range(0, len(ingredients), 3):
                row_items = ingredients[row_start:row_start+3]
                cols = st.columns(3)

                for col_idx, ingredient_name in enumerate(row_items):
                    with cols[col_idx]:
                        is_selected = ingredient_name in st.session_state.selected_ingredients

                        new_val = ingredient_card_block(
                            ingredient_name=ingredient_name,
                            is_selected=is_selected,
                            checkbox_key=f"ingredient_{ingredient_name}"
                        )

                        # 상태 업데이트
                        if new_val and (ingredient_name not in st.session_state.selected_ingredients):
                            if len(st.session_state.selected_ingredients) < 9:
                                st.session_state.selected_ingredients.append(ingredient_name)
                            else:
                                st.warning("최대 9개까지만 선택할 수 있습니다.")
                        elif (not new_val) and (ingredient_name in st.session_state.selected_ingredients):
                            st.session_state.selected_ingredients.remove(ingredient_name)

            # 카테고리 내 요약
            cat_selected = [
                x for x in st.session_state.selected_ingredients
                if x in ingredients
            ]
            if len(cat_selected) == 0:
                st.info("이 카테고리에서 아직 선택한 항목이 없습니다.")
            else:
                st.success("이 카테고리에서 선택됨: " + " / ".join(cat_selected))

    st.markdown("<hr style='margin-top:24px;margin-bottom:16px;'>", unsafe_allow_html=True)

    col_left, col_mid, col_right = st.columns([1,1,1])

    with col_left:
        if st.button("선택 초기화", use_container_width=True):
            st.session_state.selected_ingredients = []
            st.session_state.selected_menus = {}
            st.experimental_rerun()

    with col_mid:
        st.write(f"현재 {len(st.session_state.selected_ingredients)}개 선택됨")

    with col_right:
        can_go_next = (3 <= len(st.session_state.selected_ingredients) <= 9)
        if st.button("다음 단계 →", use_container_width=True, disabled=not can_go_next):
            if can_go_next:
                st.session_state.selected_menus = {
                    ing: [] for ing in st.session_state.selected_ingredients
                }
                st.session_state.step = 'menus'
                st.rerun()


# ---- 메뉴 카드 (라이트 스타일 기준) ----
def menu_card_block(menu_name: str, is_selected: bool, checkbox_key: str, ingredient_label: str):
    menu_class = "menu-card-box selected" if is_selected else "menu-card-box"

    st.markdown(
        f"""
        <div class="{menu_class}">
            <div class="card-label">{menu_name}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    new_val = st.checkbox(
        "선택",
        value=is_selected,
        key=checkbox_key,
        help=f"'{ingredient_label}' 재료의 '{menu_name}' 메뉴 선택"
    )
    return new_val


# ---- 메뉴 선택 단계 ----
def show_menu_selection():
    st.subheader("🍽️ 선호 메뉴 선택")
    st.markdown("선택하신 수산물로 만든 요리 중 선호하는 메뉴를 선택해주세요.")
    st.markdown("각 수산물마다 최소 1개 이상 선택해주세요.")

    with st.expander("선택하신 수산물", expanded=True):
        ingredients_text = " | ".join(
            [f"**{ingredient}**" for ingredient in st.session_state.selected_ingredients]
        )
        st.markdown(f"🏷️ {ingredients_text}", unsafe_allow_html=True)

    all_valid = True

    for ingredient in st.session_state.selected_ingredients:
        st.markdown(
            f"<h3 style='margin-top:16px; font-size:20px; font-weight:700;'>🐟 {ingredient} 요리</h3>",
            unsafe_allow_html=True
        )

        if ingredient in MENU_DATA:
            # 한 재료의 모든 메뉴 flatten
            all_menus = []
            for menu_list in MENU_DATA[ingredient].values():
                all_menus.extend(menu_list)

            # 3열 그리드로도 가능하지만 메뉴 이름이 좀 길 수도 있으니 2열 정도가 안정적
            # 여기서는 2열로 배치해볼게
            for row_start in range(0, len(all_menus), 2):
                row_items = all_menus[row_start:row_start+2]
                cols = st.columns(2)

                for col_idx, menu_name in enumerate(row_items):
                    with cols[col_idx]:
                        is_selected = menu_name in st.session_state.selected_menus.get(ingredient, [])
                        new_val = menu_card_block(
                            menu_name=menu_name,
                            is_selected=is_selected,
                            checkbox_key=f"menu_{ingredient}_{menu_name}",
                            ingredient_label=ingredient
                        )

                        # 상태 업데이트
                        if new_val and menu_name not in st.session_state.selected_menus[ingredient]:
                            st.session_state.selected_menus[ingredient].append(menu_name)
                        elif (not new_val) and (menu_name in st.session_state.selected_menus[ingredient]):
                            st.session_state.selected_menus[ingredient].remove(menu_name)

        # 유효성 체크
        menu_count = len(st.session_state.selected_menus.get(ingredient, []))
        if menu_count == 0:
            all_valid = False
            st.warning(f"⚠️ {ingredient}에 대해 최소 1개 이상의 메뉴를 선택해주세요.")
        else:
            st.success(f"✅ {ingredient}: {menu_count}개 메뉴 선택됨")

        st.markdown("<hr style='margin-top:16px;margin-bottom:16px;'>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        if st.button("← 이전 단계", use_container_width=True):
            st.session_state.step = 'ingredients'
            st.rerun()
    with col3:
        if all_valid:
            if st.button("설문 완료하기", use_container_width=True):
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
        else:
            st.button("설문 완료하기", disabled=True, use_container_width=True)


# ---- 완료 화면 ----
def show_completion():
    st.balloons()
    st.success("🎉 설문이 완료되었습니다! 소중한 의견을 주셔서 감사합니다")

    if hasattr(st.session_state, 'google_sheets_success') and st.session_state.google_sheets_success:
        st.success("✅ 데이터가 Google Sheets에 성공적으로 저장되었습니다!")
    else:
        st.warning("⚠️ Google Sheets 연결에 문제가 있어 로컬 백업 파일에 저장되었습니다.")

    with st.expander("📊 설문 결과 요약", expanded=True):
        st.markdown(f"**참여자:** {st.session_state.name}")
        st.markdown(f"**식별번호:** {st.session_state.id_number}")
        st.markdown(f"**설문 완료 시간:** {format_korean_time()}")
        
        st.markdown("### 선택하신 수산물")
        ingredients_text = " | ".join(st.session_state.selected_ingredients)
        st.markdown(f"🏷️ {ingredients_text}")
        
        st.markdown("### 선호하시는 메뉴")
        for ingredient, menus in st.session_state.selected_menus.items():
            if menus:
                menu_text = ", ".join(menus)
                st.markdown(f"**{ingredient}:** {menu_text}")

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
                    use_container_width=True
                )
    
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


# ===== 메인 =====
def main():
    # 라이트 모드 강제 스타일 주입
    st.markdown(LIGHT_FORCE_CSS, unsafe_allow_html=True)

    # 사이드바 스타일 조금만 키워서 노년층 가독성 유지
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-card" style="
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%) !important;
                color: white !important;
                border: none !important;
                box-shadow: 0 4px 10px rgba(0,0,0,0.15) !important;
            ">
                <h3 style="text-align:center; margin-bottom:10px; color:white !important;">📌 연구 정보</h3>
                <div style="background: rgba(255,255,255,0.15); padding:10px; border-radius:10px; margin-bottom:10px; color:white !important;">
                    <strong>🔹 연구명</strong><br>
                    요양원 거주 고령자 대상 건강 상태 및<br>블루푸드 식이 데이터베이스 구축
                </div>
                <div style="background: rgba(255,255,255,0.15); padding:10px; border-radius:10px; margin-bottom:10px; color:white !important;">
                    <strong>🔹 정부과제명</strong><br>
                    글로벌 블루푸드 미래리더 양성 프로젝트
                </div>
                <div style="background: rgba(255,255,255,0.15); padding:10px; border-radius:10px; color:white !important;">
                    <strong>🔹 연구 담당자</strong><br>
                    류혜리, 유정연<br>(서울대학교 농생명공학부 박사과정)
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

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
                except:
                    st.markdown("**📊 데이터 로드 오류**")
            else:
                st.info("아직 설문 데이터가 없습니다.")
            
            if st.button("🚪 로그아웃", use_container_width=True):
                st.session_state.is_admin = False
                st.session_state.show_admin_login = False
                st.rerun()

        st.markdown(
            """
            <div class="sidebar-card">
                <h3 style="text-align:center; color:#0077b6; margin-bottom:10px;">📋 설문 안내</h3>
                <p><strong>🎯 목적</strong><br>블루푸드 선호도 조사</p>
                <p><strong>⏱️ 소요시간</strong><br>약 3-5분</p>
                <p><strong>📝 설문 단계</strong><br>
                1️⃣ 참여자 정보 입력<br>
                2️⃣ 선호 수산물 선택 (3-9개)<br>
                3️⃣ 선호 블루푸드 메뉴 선택<br>
                4️⃣ 완료</p>
                <p><strong>🔒 개인정보 보호</strong><br>
                수집된 정보는 연구 목적으로만 사용되며,<br>
                개인정보는 안전하게 보호됩니다.</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown("### 📊 진행 상황")
        if st.session_state.step == 'info':
            st.progress(0.25, "1단계: 정보 입력")
        elif st.session_state.step == 'ingredients':
            st.progress(0.5, "2단계: 수산물 선택")
        elif st.session_state.step == 'menus':
            st.progress(0.75, "3단계: 메뉴 선택")
        elif st.session_state.step == 'complete':
            st.progress(1.0, "✅ 설문 완료!")

    st.title("🐟 블루푸드 선호도 조사")

    # 단계 라우팅
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
