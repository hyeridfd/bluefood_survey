import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PIL import Image
import base64
import gspread
import toml
import os
import time
import random
import traceback
from google.oauth2.service_account import Credentials

import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib as mpl
import matplotlib.font_manager as fm
from matplotlib import rcParams
from matplotlib import font_manager as fm
import urllib.request

# ✅ NanumGothic 폰트 다운로드 경로 (Streamlit Cloud에서도 사용 가능)
FONT_PATH = "/tmp/NanumGothic.ttf"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"

# ✅ 폰트 다운로드 (없으면 자동 다운로드)
if not os.path.exists(FONT_PATH):
    try:
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
    except Exception as e:
        print(f"⚠️ 폰트 다운로드 실패: {e}")

# ✅ fontprop 전역 정의
try:
    fontprop = fm.FontProperties(fname=FONT_PATH)
    rcParams['font.family'] = fontprop.get_name()
    mpl.rcParams['font.family'] = fontprop.get_name()
    mpl.rcParams['axes.unicode_minus'] = False
except Exception as e:
    print(f"⚠️ 폰트 로드 실패, 기본 폰트 사용: {e}")
    fontprop = None


def show_admin_dashboard(df):
    """관리자 대시보드: 응답 현황 시각화 및 중복 응답 감지"""
    st.markdown("## 📊 관리자 대시보드")

    if df is None or df.empty:
        st.warning("⚠️ 응답 데이터가 없습니다.")
        return

    # ✅ 1. 응답 요약 정보
    st.markdown(f"**총 응답자 수:** {df['식별번호'].nunique()}명")
    st.markdown(f"**총 응답 수:** {len(df)}건")
    st.markdown(f"**최근 응답 시간:** {df['설문일시'].max()}")

    # ✅ 2. 중복 응답 감지
    st.markdown("### 🔍 중복 응답 감지")
    dup = df[df.duplicated('식별번호', keep=False)]
    if not dup.empty:
        st.warning(f"⚠️ {dup['식별번호'].nunique()}명의 중복 응답 발견")
        st.dataframe(dup)
    else:
        st.success("✅ 중복 응답 없음")

    # ✅ 3. 수산물 선호도 TOP5
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
                sns.barplot(x=top_ing.values, y=top_ing.index, ax=ax1, palette=["#A7C7E7", "#89CFF0", "#7EC8E3", "#5DADE2", "#3498DB"])

                # ✅ fontprop이 정의되어 있을 때만 적용
                try:
                    ax1.set_title("선호 수산물 TOP5", fontproperties=fontprop)
                    ax1.set_xlabel("응답 수", fontproperties=fontprop)
                    ax1.set_ylabel("수산물", fontproperties=fontprop)

                # ✅ y축 ticklabel (수산물 이름) 폰트 적용
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


    # --- 4. 메뉴 선호도 ---
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
                sns.barplot(x=top_menu.values, y=top_menu.index, ax=ax2, palette=["#A7C7E7", "#89CFF0", "#7EC8E3", "#5DADE2", "#3498DB"])
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

    # --- 5. 날짜별 응답 추이 ---
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
                ax3.set_title("날짜별 응답 추이", fontproperties=fontprop)
                ax3.set_xlabel("날짜", fontproperties=fontprop)
                ax3.set_ylabel("응답 수", fontproperties=fontprop)

                ax3.grid(True, linestyle="--", alpha=0.5)
                fig3.autofmt_xdate()
                st.pyplot(fig3)
            else:
                st.info("📌 날짜별 데이터가 없습니다.")
        except Exception as e:
            st.error(f"데이터 로드 오류 (날짜): {e}")
    
# ✅ 한국 시간대 설정
KST = timezone(timedelta(hours=9))

# ✅ 관리자 패스워드 설정
ADMIN_PASSWORD = "bluefood2025"

def get_korean_time():
    """한국 시간(KST)을 반환하는 함수"""
    return datetime.now(KST)

def format_korean_time():
    """한국 시간을 문자열로 포맷팅"""
    return get_korean_time().strftime('%Y-%m-%d %H:%M:%S')


#@st.cache_resource
def get_google_sheet_cached():
    """개선된 Google Sheets 연결 함수"""
    # 디버깅 정보를 항상 표시하도록 수정
    debug_container = st.empty()
    with debug_container.container():
        #st.write("🟢 [DEBUG] Google Sheets 연결 시도 시작됨")
        
        try:
            # Secrets 확인
            if "gcp_service_account" not in st.secrets:
                st.error("❌ [DEBUG] gcp_service_account 누락")
                return None
            
            if "google_sheets" not in st.secrets:
                st.error("❌ [DEBUG] google_sheets 설정 누락")
                return None
            
            # 서비스 계정 정보 가져오기
            creds_dict = dict(st.secrets["gcp_service_account"])
            #st.write("🟢 [DEBUG] 서비스 계정 이메일:", creds_dict.get("client_email", "없음"))
            #st.write("🟢 [DEBUG] 프로젝트 ID:", creds_dict.get("project_id", "없음"))

            # private_key 줄바꿈 변환 확인
            if "private_key" in creds_dict:
                original_key = creds_dict["private_key"]
                if "\\n" in original_key:
                    creds_dict["private_key"] = original_key.replace("\\n", "\n")
                    #st.write("🟢 [DEBUG] private_key 줄바꿈 변환 완료")
                else:
                    st.write("🟢 [DEBUG] private_key 이미 올바른 형태")
                
                #st.write("🟢 [DEBUG] private_key 길이:", len(creds_dict["private_key"]))
                #st.write("🟢 [DEBUG] private_key 시작:", creds_dict["private_key"][:50] + "...")
                #st.write("🟢 [DEBUG] private_key 끝:", "..." + creds_dict["private_key"][-50:])

            # Google Sheets 설정
            google_sheets_config = st.secrets["google_sheets"]
            sheet_name = google_sheets_config.get("google_sheet_name")
            sheet_id = google_sheets_config.get("google_sheet_id")
            
            #st.write("🟢 [DEBUG] 구글 시트 이름:", sheet_name)
            #st.write("🟢 [DEBUG] 구글 시트 ID:", sheet_id)

            # Scope 설정
            scope = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Credentials 생성
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            #st.write("🟢 [DEBUG] Credentials 객체 생성 성공")
            
            # gspread 클라이언트 생성
            client = gspread.authorize(creds)
            #st.write("🟢 [DEBUG] gspread 클라이언트 인증 성공")
            
            # 구글 시트 열기 시도
            try:
                # ID로 열기 시도
                if sheet_id:
                    sheet = client.open_by_key(sheet_id)
                    #st.write("🟢 [DEBUG] Sheet ID로 연결 성공:", sheet_id)
                # 이름으로 열기
                elif sheet_name:
                    sheet = client.open(sheet_name)
                    #st.write("🟢 [DEBUG] Sheet 이름으로 연결 성공:", sheet_name)
                else:
                    #st.error("❌ [DEBUG] Sheet ID와 이름 모두 누락")
                    return None
                
                st.success("✅ [DEBUG] Google Sheets 연결 완료!")
                
                # 워크시트 정보
                worksheet = sheet.get_worksheet(0)
                #st.write(f"🟢 [DEBUG] 첫 번째 워크시트: {worksheet.title}")
                
                # worksheet만 반환
                return worksheet
                
            except gspread.SpreadsheetNotFound as e:
                st.error(f"❌ [DEBUG] 시트를 찾을 수 없음: {e}")
                st.error(f"❌ [DEBUG] 시트 ID: {sheet_id}")
                st.error(f"❌ [DEBUG] 시트 이름: {sheet_name}")
                return None
            
        except Exception as e:
            st.error(f"❌ [DEBUG] 연결 오류: {type(e).__name__}: {e}")
            st.error(f"❌ [DEBUG] 전체 스택 트레이스:")
            st.error(traceback.format_exc())
            return None
    

def save_to_google_sheets(name, id_number, ingredients, menus):
    """Google Sheets에 데이터 저장"""
    success = False
    timestamp = format_korean_time()
    
    try:
        # worksheet 가져오기
        worksheet = get_google_sheet_cached()
        
        if worksheet is None:
            st.error("❌ [DEBUG] Google Sheets worksheet를 가져올 수 없습니다.")
            return success
        
        # 메뉴 문자열 생성
        menu_strings = []
        for ingredient, menu_list in menus.items():
            if menu_list:
                menu_text = f"{ingredient}: {', '.join(menu_list)}"
                menu_strings.append(menu_text)
        menu_string = " | ".join(menu_strings) if menu_strings else ""
        
        # 새 데이터 행
        new_row = [
            timestamp,                        # 설문일시
            name,                             # 이름
            id_number,                        # 식별번호
            ", ".join(ingredients),           # 선택한_수산물
            menu_string                       # 선택한_메뉴
        ]
        
        st.write(f"🟡 [DEBUG] 저장할 데이터: {new_row}")
        
        # 현재 행 수 확인
        all_values = worksheet.get_all_values()
        
        # 헤더가 없으면 추가
        if len(all_values) == 0 or all_values[0] != ["설문일시", "이름", "식별번호", "선택한_수산물", "선택한_메뉴"]:
            worksheet.insert_row(["설문일시", "이름", "식별번호", "선택한_수산물", "선택한_메뉴"], 1)
            #st.write("🟢 [DEBUG] 헤더 행 추가 완료")
        
        # 데이터 추가
        worksheet.append_row(new_row)
        #st.success(f"✅ [DEBUG] Google Sheets 저장 성공! (행 {len(all_values) + 1})")
        success = True
        
    except Exception as e:
        st.error(f"❌ [DEBUG] Google Sheets 저장 실패: {e}")
        st.error(f"❌ [DEBUG] 상세 오류:\n{traceback.format_exc()}")
    
    return success


def save_to_excel(name, id_number, ingredients, menus):
    """설문 결과를 엑셀 파일로 저장"""
    # 데이터 준비
    timestamp = format_korean_time()
    
    # 메뉴 문자열 생성
    menu_strings = []
    for ingredient, menu_list in menus.items():
        if menu_list:
            menu_text = f"{ingredient}: {', '.join(menu_list)}"
            menu_strings.append(menu_text)
    
    menu_string = " | ".join(menu_strings) if menu_strings else ""
    
    # 새로운 데이터 행
    new_data = {
        "설문일시": timestamp,
        "이름": name,
        "식별번호": id_number,
        "선택한_수산물": ", ".join(ingredients),
        "선택한_메뉴": menu_string
    }
    
    # 엑셀 파일 경로
    excel_dir = Path("survey_results")
    excel_dir.mkdir(exist_ok=True)
    filename = excel_dir / f"bluefood_survey_{datetime.now().strftime('%Y%m%d')}.xlsx"
    
    # 기존 파일이 있으면 불러오기
    if filename.exists():
        df = pd.read_excel(filename)
        df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    else:
        df = pd.DataFrame([new_data])
    
    # Google Sheets 저장 시도
    google_sheets_success = save_to_google_sheets(name, id_number, ingredients, menus)
    st.session_state.google_sheets_success = google_sheets_success
    
    # 로컬 백업 저장
    df.to_excel(filename, index=False)
    
    return str(filename), df

# 이미지 경로 설정
INGREDIENT_IMAGE_PATH = "images/ingredients"
MENU_IMAGE_PATH = "images/menus"

# 수산물 카테고리별 분류
INGREDIENT_CATEGORIES = {
    '🍤 가공수산물': ['맛살', '어란', '어묵', '쥐포'],
    '🌿 해조류': ['김', '다시마', '매생이', '미역', '파래', '톳'],
    '🦑 연체류': ['꼴뚜기', '낙지', '문어', '오징어', '주꾸미'],
    '🦀 갑각류': ['가재', '게', '새우'],
    '🐚 패류': ['다슬기', '꼬막', '가리비', '골뱅이', '굴', '미더덕', '바지락', '백합', '소라', '재첩', '전복', '홍합'],
    '🐟 어류': ['가자미', '다랑어', '고등어', '갈치', '꽁치', '대구', '멸치', '명태', '박대', '뱅어', '병어', '삼치', '아귀', '연어', '임연수', '장어', '조기']
}

# 수산물별 메뉴 데이터
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

def main():
    # 페이지 기본 설정
    st.set_page_config(
        page_title="블루푸드 선호도 조사",
        page_icon="🐟",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # CSS 스타일
    st.markdown("""
    <style>
    /* 기본 여백 조정 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* 헤더 스타일 */
    .main-header {
        text-align: center;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        background-color: #45a049;
        transform: scale(1.05);
    }
    
    /* 체크박스 라벨 텍스트를 진하게 */
    .stCheckbox > label {
        font-weight: 600;
        font-size: 16px;
    }
    
    /* 진행 상황 표시 스타일 */
    .progress-container {
        display: flex;
        justify-content: center;
        margin: 2rem 0;
    }
    
    .progress-step {
        padding: 0.5rem 1rem;
        margin: 0 0.5rem;
        border-radius: 20px;
        background: #e0e0e0;
        font-weight: bold;
    }
    
    .progress-step.active {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    /* 수산물/메뉴 선택 체크박스 컨테이너 */
    div[data-testid="column"] > div > div > div > div[data-testid="stCheckbox"] {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
        transition: all 0.3s;
    }
    
    div[data-testid="column"] > div > div > div > div[data-testid="stCheckbox"]:hover {
        background-color: #e9ecef;
        transform: translateX(5px);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 세션 상태 초기화
    if 'step' not in st.session_state:
        st.session_state.step = 'info'
    if 'name' not in st.session_state:
        st.session_state.name = ''
    if 'id_number' not in st.session_state:
        st.session_state.id_number = ''
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
    
    # 메인 헤더
    st.markdown("""
    <div class="main-header">
        <h1>🐟 블루푸드 선호도 조사 🐟</h1>
        <p>맛있고 건강한 수산물 요리, 당신의 선택은?</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 진행 상황 표시
    steps = {
        'info': '개인정보 입력',
        'ingredients': '수산물 선택',
        'menu': '메뉴 선택',
        'complete': '완료'
    }
    
    progress_html = '<div class="progress-container">'
    for key, label in steps.items():
        active_class = 'active' if key == st.session_state.step else ''
        progress_html += f'<div class="progress-step {active_class}">{label}</div>'
    progress_html += '</div>'
    st.markdown(progress_html, unsafe_allow_html=True)
    
    # 사이드바 - 관리자 로그인
    with st.sidebar:
        st.markdown("### 🔐 관리자 모드")
        
        # 관리자 로그인 토글
        if st.button("관리자 로그인" if not st.session_state.is_admin else "관리자 로그아웃"):
            st.session_state.show_admin_login = not st.session_state.show_admin_login
            if st.session_state.is_admin:  # 로그아웃
                st.session_state.is_admin = False
                st.rerun()
        
        # 로그인 폼
        if st.session_state.show_admin_login and not st.session_state.is_admin:
            password = st.text_input("패스워드", type="password")
            if st.button("로그인"):
                if password == ADMIN_PASSWORD:
                    st.session_state.is_admin = True
                    st.success("✅ 관리자 로그인 성공!")
                    st.rerun()
                else:
                    st.error("❌ 패스워드가 틀렸습니다.")
        
        # 관리자 메뉴
        if st.session_state.is_admin:
            st.success("🔓 관리자 모드 활성화")
            
            if st.button("📊 대시보드 보기"):
                st.session_state.step = 'admin_dashboard'
                st.rerun()
            
            if st.button("📥 응답 데이터 보기"):
                st.session_state.step = 'admin_responses'
                st.rerun()
            
            if st.button("🏠 메인으로 돌아가기"):
                st.session_state.step = 'info'
                st.rerun()
    
    # 관리자 대시보드 표시
    if st.session_state.is_admin and st.session_state.step == 'admin_dashboard':
        # Google Sheets에서 데이터 가져오기
        worksheet = get_google_sheet_cached()
        
        if worksheet:
            try:
                all_data = worksheet.get_all_values()
                if len(all_data) > 1:
                    df = pd.DataFrame(all_data[1:], columns=all_data[0])
                    show_admin_dashboard(df)
                else:
                    st.warning("아직 응답 데이터가 없습니다.")
            except Exception as e:
                st.error(f"데이터 로드 실패: {e}")
        else:
            # 로컬 파일에서 데이터 로드 시도
            excel_dir = Path("survey_results")
            if excel_dir.exists():
                excel_files = list(excel_dir.glob("*.xlsx"))
                if excel_files:
                    all_data = []
                    for file in excel_files:
                        df = pd.read_excel(file)
                        all_data.append(df)
                    if all_data:
                        combined_df = pd.concat(all_data, ignore_index=True)
                        show_admin_dashboard(combined_df)
                else:
                    st.warning("아직 응답 데이터가 없습니다.")
    
    # 관리자 응답 데이터 보기
    elif st.session_state.is_admin and st.session_state.step == 'admin_responses':
        st.subheader("📥 전체 응답 데이터")
        
        # Google Sheets에서 데이터 가져오기
        worksheet = get_google_sheet_cached()
        
        if worksheet:
            try:
                all_data = worksheet.get_all_values()
                if len(all_data) > 1:
                    df = pd.DataFrame(all_data[1:], columns=all_data[0])
                    st.dataframe(df, use_container_width=True)
                    
                    # 엑셀 다운로드
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        "📥 CSV로 다운로드",
                        csv,
                        f"survey_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        "text/csv",
                        key='download-csv'
                    )
                else:
                    st.warning("아직 응답 데이터가 없습니다.")
            except Exception as e:
                st.error(f"데이터 로드 실패: {e}")
        else:
            st.warning("Google Sheets 연결 실패. 로컬 백업 파일을 확인하세요.")
    
    # 일반 사용자 플로우
    elif st.session_state.step == 'info':
        show_info_input()
    elif st.session_state.step == 'ingredients':
        show_ingredient_selection()
    elif st.session_state.step == 'menu':
        show_menu_selection()
    elif st.session_state.step == 'complete':
        show_completion()

def show_info_input():
    st.subheader("📝 참여자 정보 입력")
    
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("이름", value=st.session_state.name)
    with col2:
        id_number = st.text_input("식별번호 (예: 학번, 사원번호 등)", value=st.session_state.id_number)
    
    # Google Sheets 연결 상태 표시
    st.markdown("---")
    st.markdown("#### 🔗 데이터베이스 연결 상태")
    worksheet = get_google_sheet_cached()
    if worksheet:
        st.success("✅ Google Sheets 연결 성공! 실시간 데이터 저장이 가능합니다.")
    else:
        st.warning("⚠️ Google Sheets 연결 실패. 데이터는 로컬 백업 파일에 저장됩니다.")
    
    st.markdown("---")
    
    if st.button("다음 단계로 →", type="primary", use_container_width=True):
        if name and id_number:
            st.session_state.name = name
            st.session_state.id_number = id_number
            st.session_state.step = 'ingredients'
            st.rerun()
        else:
            st.error("모든 정보를 입력해주세요.")

def render_image_fixed_size(img_path, width=180, height=120, placeholder="🐟"):
    """이미지를 고정 크기로 출력, 없으면 플레이스홀더"""
    if os.path.exists(img_path):
        with open(img_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
        return f"""
        <div style="
            width:{width}px; 
            height:{height}px; 
            overflow:hidden; 
            border-radius:8px; 
            border:1px solid #ddd; 
            display:flex; 
            align-items:center; 
            justify-content:center; 
            background:#fff;">
            <img src="data:image/png;base64,{img_data}" 
                 style="width:100%; height:100%; object-fit:cover;">
        </div>
        """
    else:
        return f"""
        <div style="
            width:{width}px; 
            height:{height}px; 
            background:#f8f9fa; 
            border:2px dashed #dee2e6; 
            border-radius:8px; 
            display:flex; 
            flex-direction:column;
            align-items:center; 
            justify-content:center; 
            color:#6c757d;">
            <div style="font-size:1.5em;">{placeholder}</div>
            <div style="font-size:0.8em;">이미지 준비중</div>
        </div>
        """
        
def show_ingredient_selection():
    st.subheader("🐟 선호하는 수산물 선택")
    st.info("💡 **최소 3개 이상** 선택해주세요! 다양한 수산물을 선택하실수록 더 좋습니다.")
    
    # 수산물 카테고리별 분류
    categories = {
    '🍤 가공수산물': ['맛살', '어란', '어묵', '쥐포'],
    '🌿 해조류': ['김', '다시마', '매생이', '미역', '파래', '톳'],
    '🦑 연체류': ['꼴뚜기', '낙지', '문어', '오징어', '주꾸미'],
    '🦀 갑각류': ['가재', '게', '새우'],
    '🐚 패류': ['다슬기', '꼬막', '가리비', '골뱅이', '굴', '미더덕', '바지락', '백합', '소라', '재첩', '전복', '홍합'],
    '🐟 어류': ['가자미', '다랑어', '고등어', '갈치', '꽁치', '대구', '멸치', '명태', '박대', '뱅어', '병어', '삼치', '아귀', '연어', '임연수', '장어', '조기']
}
    
    # 이전 선택 복원
    selected = st.session_state.selected_ingredients.copy()
    
    # 카테고리별로 표시 (텍스트로만 표시)
    for category, items in categories.items():
        st.markdown(f"### {category}")
        
        # 4개씩 가로 배치 (텍스트 체크박스로 변경)
        for row_start in range(0, len(items), 4):
            cols = st.columns(4)
            for col_idx, item in enumerate(items[row_start:row_start+4]):
                with cols[col_idx]:
                    # 텍스트와 체크박스로 표시
                    st.markdown(f"<div style='text-align:center; font-size:20px; font-weight:bold; padding:10px; background:#f0f8ff; border-radius:10px; margin-bottom:5px;'>{item}</div>", unsafe_allow_html=True)
                    
                    # 체크박스 중앙 정렬
                    col_left, col_center, col_right = st.columns([1, 2, 1])
                    with col_center:
                        if st.checkbox("선택", value=(item in selected), key=f"ingredient_{item}"):
                            if item not in selected:
                                selected.append(item)
                        else:
                            if item in selected:
                                selected.remove(item)
    
    # 선택 상태 업데이트
    st.session_state.selected_ingredients = selected
    
    # 선택 현황 표시
    st.markdown("---")
    if selected:
        st.success(f"✅ 현재 {len(selected)}개 선택됨: {', '.join(selected)}")
    else:
        st.warning("⚠️ 수산물을 선택해주세요.")
    
    # 버튼들
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← 이전 단계", use_container_width=True):
            st.session_state.step = 'info'
            st.rerun()
    
    with col3:
        if len(selected) >= 3:
            if st.button("다음 단계로 →", type="primary", use_container_width=True):
                # 선택된 수산물에 대한 메뉴 초기화
                for ingredient in selected:
                    if ingredient not in st.session_state.selected_menus:
                        st.session_state.selected_menus[ingredient] = []
                
                # 선택 해제된 수산물 제거
                to_remove = []
                for ingredient in st.session_state.selected_menus:
                    if ingredient not in selected:
                        to_remove.append(ingredient)
                for ingredient in to_remove:
                    del st.session_state.selected_menus[ingredient]
                
                st.session_state.step = 'menu'
                st.rerun()
        else:
            st.button(f"다음 단계로 → (최소 3개 선택)", disabled=True, use_container_width=True)
            if selected:
                st.info(f"💡 {3 - len(selected)}개를 더 선택해주세요.")

@st.cache_data
def get_menu_image_html(menu):
    """이미지를 캐시하여 반복 로딩 방지"""
    png_path = os.path.join(MENU_IMAGE_PATH, f"{menu}.png")
    jpg_path = os.path.join(MENU_IMAGE_PATH, f"{menu}.jpg")

    if os.path.exists(png_path):
        return render_image_fixed_size(png_path, width=240, height=180, placeholder="🍽️") 
    elif os.path.exists(jpg_path):
        return render_image_fixed_size(jpg_path, width=240, height=180, placeholder="🍽️")
    else:
        return render_image_fixed_size("", width=240, height=180, placeholder="🍽️")

def display_menu_optimized(menu, ingredient, is_selected, key):
    """최적화된 메뉴 표시 함수 - CSS 중복 제거, 이미지 캐싱"""
    
    # 캐시된 이미지 HTML 사용
    html_img = get_menu_image_html(menu)

    with st.container():
        # 메뉴명 중앙 정렬
        st.markdown(
            f"<div style='text-align:center; margin-bottom:5px;'><strong style='font-size:18px;'>{menu}</strong></div>",
            unsafe_allow_html=True
        )

        # 이미지 중앙
        st.markdown(f"<div style='display:flex; justify-content:center;'>{html_img}</div>", unsafe_allow_html=True)

        # 체크박스 중앙
        col_left, col_center, col_right = st.columns([1, 2, 1])
        with col_center:
            checkbox_result = st.checkbox("선택", value=is_selected, key=key)

        return checkbox_result


def show_menu_selection():
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
    st.info("**🔸 선택하신 수산물로 만든 요리 중 선호하는 메뉴를 선택해주세요**\n\n✓ 각 수산물마다 최소 1개 이상의 메뉴를 선택해주세요")

    with st.expander("선택하신 수산물", expanded=True):
        ingredients_text = " | ".join([f"**{ingredient}**" for ingredient in st.session_state.selected_ingredients])
        st.markdown(f"🏷️ {ingredients_text}")

    # CSS를 한 번만 적용 (성능 최적화)
    st.markdown("""
    <style>
    /* 메뉴 체크박스 버튼 스타일 */
    div.stCheckbox {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-top: 6px;
    }
    div.stCheckbox > label {
        background: #f8f9fa;
        border: 2px solid #ccc;
        border-radius: 10px;
        padding: 8px 20px;
        cursor: pointer;
        font-size: 18px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    div.stCheckbox > label:has(input:checked) {
        background: linear-gradient(135deg, #4facfe, #00f2fe);
        border-color: #0096c7;
        color: white;
    }
    div.stCheckbox input[type="checkbox"] {
        transform: scale(1.5);
        margin-right: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

    all_valid = True

    # 각 수산물별 메뉴 처리 (st.rerun() 제거로 성능 최적화)
    for ingredient in st.session_state.selected_ingredients:
        st.markdown(f"### 🐟 {ingredient} 요리")

        if ingredient in MENU_DATA:
            # 메뉴 리스트 생성
            all_menus = []
            for menu_list in MENU_DATA[ingredient].values():
                all_menus.extend(menu_list)

            # 4개씩 가로 배치
            for row_start in range(0, len(all_menus), 4):
                cols = st.columns(4)
                for col_idx, menu in enumerate(all_menus[row_start:row_start+4]):
                    with cols[col_idx]:
                        # 최적화된 메뉴 표시 함수 사용
                        is_selected = menu in st.session_state.selected_menus.get(ingredient, [])
                        selected = display_menu_optimized(menu, ingredient, is_selected, f"menu_{ingredient}_{menu}")
                        
                        # st.rerun() 없이 상태 업데이트 (즉시 반응하지만 새로고침 없음)
                        if selected and menu not in st.session_state.selected_menus[ingredient]:
                            st.session_state.selected_menus[ingredient].append(menu)
                        elif not selected and menu in st.session_state.selected_menus[ingredient]:
                            st.session_state.selected_menus[ingredient].remove(menu)

        # 선택 여부 확인
        menu_count = len(st.session_state.selected_menus.get(ingredient, []))
        if menu_count == 0:
            all_valid = False
            st.warning(f"⚠️ {ingredient}에 대해 최소 1개 이상의 메뉴를 선택해주세요.")
        else:
            st.success(f"✅ {ingredient}: {menu_count}개 메뉴 선택됨")

        st.markdown("---")

    # 버튼들 (st.rerun()은 페이지 전환 시에만 사용)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← 이전 단계", use_container_width=True):
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

    with col3:
        if all_valid:
            if st.button("설문 완료하기", type="primary", use_container_width=True):
                # ✅ 저장 실행
                filename, df = save_to_excel(
                    st.session_state.name,
                    st.session_state.id_number,
                    st.session_state.selected_ingredients,
                    st.session_state.selected_menus
                )
    
                # ✅ 저장 성공 여부에 따라 상태 업데이트
                if filename is not None or st.session_state.get("google_sheets_success", False):
                    st.session_state.already_saved = True
                    st.session_state.filename = filename
                    st.session_state.survey_data = df
                    st.session_state.step = 'complete'
                    st.rerun()   # 🔥 페이지 즉시 전환
                else:
                    st.error("❌ 설문 데이터 저장에 실패했습니다. 다시 시도해주세요.")
        else:
            st.button("설문 완료하기", disabled=True, use_container_width=True)

def show_menu_selection():
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
    st.info("**🔸 선택하신 수산물로 만든 요리 중 선호하는 메뉴를 선택해주세요**\n\n✓ 각 수산물마다 최소 1개 이상의 메뉴를 선택해주세요")

    with st.expander("선택하신 수산물", expanded=True):
        ingredients_text = " | ".join([f"**{ingredient}**" for ingredient in st.session_state.selected_ingredients])
        st.markdown(f"🏷️ {ingredients_text}")

    # CSS를 한 번만 적용 (성능 최적화)
    st.markdown("""
    <style>
    /* 메뉴 체크박스 버튼 스타일 */
    div.stCheckbox {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-top: 6px;
    }
    div.stCheckbox > label {
        background: #f8f9fa;
        border: 2px solid #ccc;
        border-radius: 10px;
        padding: 8px 20px;
        cursor: pointer;
        font-size: 18px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    div.stCheckbox > label:has(input:checked) {
        background: linear-gradient(135deg, #4facfe, #00f2fe);
        border-color: #0096c7;
        color: white;
    }
    div.stCheckbox input[type="checkbox"] {
        transform: scale(1.5);
        margin-right: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

    all_valid = True

    # 각 수산물별 메뉴 처리 (st.rerun() 제거로 성능 최적화)
    for ingredient in st.session_state.selected_ingredients:
        st.markdown(f"### 🐟 {ingredient} 요리")

        if ingredient in MENU_DATA:
            # 메뉴 리스트 생성
            all_menus = []
            for menu_list in MENU_DATA[ingredient].values():
                all_menus.extend(menu_list)

            # 4개씩 가로 배치
            for row_start in range(0, len(all_menus), 4):
                cols = st.columns(4)
                for col_idx, menu in enumerate(all_menus[row_start:row_start+4]):
                    with cols[col_idx]:
                        # 최적화된 메뉴 표시 함수 사용
                        is_selected = menu in st.session_state.selected_menus.get(ingredient, [])
                        selected = display_menu_optimized(menu, ingredient, is_selected, f"menu_{ingredient}_{menu}")
                        
                        # st.rerun() 없이 상태 업데이트 (즉시 반응하지만 새로고침 없음)
                        if selected and menu not in st.session_state.selected_menus[ingredient]:
                            st.session_state.selected_menus[ingredient].append(menu)
                        elif not selected and menu in st.session_state.selected_menus[ingredient]:
                            st.session_state.selected_menus[ingredient].remove(menu)

        # 선택 여부 확인
        menu_count = len(st.session_state.selected_menus.get(ingredient, []))
        if menu_count == 0:
            all_valid = False
            st.warning(f"⚠️ {ingredient}에 대해 최소 1개 이상의 메뉴를 선택해주세요.")
        else:
            st.success(f"✅ {ingredient}: {menu_count}개 메뉴 선택됨")

        st.markdown("---")

    # 버튼들 (st.rerun()은 페이지 전환 시에만 사용)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← 이전 단계", use_container_width=True):
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

    with col3:
        if all_valid:
            if st.button("설문 완료하기", type="primary", use_container_width=True):
                # ✅ 저장 실행
                filename, df = save_to_excel(
                    st.session_state.name,
                    st.session_state.id_number,
                    st.session_state.selected_ingredients,
                    st.session_state.selected_menus
                )
    
                # ✅ 저장 성공 여부에 따라 상태 업데이트
                if filename is not None or st.session_state.get("google_sheets_success", False):
                    st.session_state.already_saved = True
                    st.session_state.filename = filename
                    st.session_state.survey_data = df
                    st.session_state.step = 'complete'
                    st.rerun()   # 🔥 페이지 즉시 전환
                else:
                    st.error("❌ 설문 데이터 저장에 실패했습니다. 다시 시도해주세요.")
        else:
            st.button("설문 완료하기", disabled=True, use_container_width=True)

def show_completion():
    # 스크롤 상단 이동
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
    st.success("🎉 설문이 완료되었습니다! 소중한 의견을 주셔서 감사합니다")
    
    # Google Sheets 연동 결과 표시
    if hasattr(st.session_state, 'google_sheets_success') and st.session_state.google_sheets_success:
        st.success("✅ 데이터가 Google Sheets에 성공적으로 저장되었습니다!")
    else:
        st.warning("⚠️ Google Sheets 연결에 문제가 있어 로컬 백업 파일에 저장되었습니다.")
    
    # 결과 요약 표시
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
    
    # 관리자만 다운로드 버튼 표시
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
    
    # 새 설문 시작 버튼
    if st.button("🔄 새 설문 시작하기", use_container_width=True):
        # 세션 상태 초기화 (관리자 상태는 유지)
        admin_status = st.session_state.is_admin
        admin_login_status = st.session_state.show_admin_login
        
        # 모든 키 삭제 후 필요한 것만 복원
        keys_to_keep = ['is_admin', 'show_admin_login']
        for key in list(st.session_state.keys()):
            if key not in keys_to_keep:
                del st.session_state[key]
        
        # 기본 상태 재설정
        st.session_state.is_admin = admin_status
        st.session_state.show_admin_login = admin_login_status
        st.session_state.step = 'info'
        st.session_state.selected_ingredients = []
        st.session_state.selected_menus = {}
        st.session_state.already_saved = False
        
        st.rerun()

if __name__ == "__main__":
    main()
