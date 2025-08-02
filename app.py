import streamlit as st
import os
from PIL import Image
import base64
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="블루푸드 선호도 조사", page_icon="🌊", layout="wide")

# ✅ 카테고리별 수산물
INGREDIENT_CATEGORIES = {
    '🍤 가공수산물': ['맛살', '어란', '어묵', '쥐포'],
    '🌿 해조류': ['김', '다시마', '매생이', '미역', '파래', '톳'],
    '🦑 연체류': ['꼴뚜기', '낙지', '문어', '오징어', '주꾸미'],
    '🦀 갑각류': ['가재', '게', '새우'],
    '🐚 패류': ['다슬기', '꼬막', '가리비', '골뱅이', '굴', '미더덕', '바지락', '백합', '소라', '재첩', '전복', '홍합'],
    '🐟 어류': ['가자미', '다랑어', '고등어', '갈치', '꽁치', '대구', '멸치', '명태', '박대', '뱅어', '병어', '삼치', '아귀', '연어', '임연수', '장어', '조기']
}

IMAGE_PATH = "images/ingredients"
MENU_IMAGE_PATH = "images/menus"

# ✅ 메뉴 데이터 예시 (간단)
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

# ✅ 세션 초기화
if "step" not in st.session_state:
    st.session_state.step = "info"
if "selected_ingredients" not in st.session_state:
    st.session_state.selected_ingredients = []
if "selected_menus" not in st.session_state:
    st.session_state.selected_menus = {}

# ✅ CSS 스타일 (HTML 디자인 참고)
st.markdown("""
<style>
body { background: #fafafa; }
.category-title {
    background:linear-gradient(135deg,#667eea,#764ba2);
    color:white; text-align:center; font-size:1.3em; font-weight:600;
    padding:10px; border-radius:8px; margin:25px 0 10px;
}
.ingredient-grid, .menu-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
}
.card {
    background: #f8f9fa; border:2px solid #e9ecef; border-radius:10px;
    padding:10px; text-align:center; cursor:pointer;
    transition: all 0.3s ease; box-shadow:0 3px 8px rgba(0,0,0,0.05);
}
.card:hover { transform:translateY(-3px); box-shadow:0 6px 15px rgba(0,0,0,0.1); }
.card img { width:200px; height:120px; object-fit:cover; border-radius:8px; }
.card p { font-weight:600; font-size:1.1em; margin-top:5px; }
.card.selected { background:linear-gradient(135deg,#667eea,#764ba2); color:white; border-color:#667eea; }
</style>
""", unsafe_allow_html=True)

# ✅ 이미지 Base64 변환
def image_to_base64(img):
    if img is None:
        return ""
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# ✅ 이미지 로드
def load_img(path):
    return Image.open(path) if os.path.exists(path) else None

# ✅ 재료 카드 렌더링
def render_card(label, img, is_selected):
    img64 = image_to_base64(img) if img else ""
    cls = "card selected" if is_selected else "card"
    return f"""
    <div class="{cls}">
        <img src="data:image/png;base64,{img64}">
        <p>{label}</p>
    </div>
    """

# ✅ 1단계: 참여자 정보 입력
def show_info():
    st.title("🌊 블루푸드 선호도 조사")
    name = st.text_input("성함", placeholder="홍길동")
    idn = st.text_input("식별번호", placeholder="예: 2024001")
    if st.button("설문 시작하기", type="primary"):
        if name and idn:
            st.session_state.name = name
            st.session_state.idn = idn
            st.session_state.step = "ingredients"
            st.rerun()
        else:
            st.error("⚠️ 성함과 식별번호를 입력해주세요.")

# ✅ 2단계: 수산물 선택
def show_ingredients():
    st.subheader("🐟 수산물 원재료 선택")
    st.info("최소 3개 이상, 최대 9개까지 선택해주세요.")

    for category, items in INGREDIENT_CATEGORIES.items():
        st.markdown(f"<div class='category-title'>{category}</div>", unsafe_allow_html=True)
        st.markdown("<div class='ingredient-grid'>", unsafe_allow_html=True)

        for ingredient in items:
            jpg = os.path.join(IMAGE_PATH, f"{ingredient}.jpg")
            png = os.path.join(IMAGE_PATH, f"{ingredient}.png")
            img = load_img(jpg) or load_img(png)
            selected = ingredient in st.session_state.selected_ingredients

            if st.button(f"선택_{ingredient}", key=f"ing_btn_{ingredient}"):
                if selected:
                    st.session_state.selected_ingredients.remove(ingredient)
                else:
                    if len(st.session_state.selected_ingredients) < 9:
                        st.session_state.selected_ingredients.append(ingredient)
                    else:
                        st.warning("❌ 최대 9개까지 선택 가능")
                st.rerun()

            st.markdown(render_card(ingredient, img, selected), unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # ✅ 상태 표시
    count = len(st.session_state.selected_ingredients)
    if 3 <= count <= 9:
        st.success(f"✅ 현재 {count}개 선택됨")
    elif count < 3:
        st.warning(f"⚠️ {count}개 선택됨 (3개 이상 필요)")
    else:
        st.error(f"❌ {count}개 선택됨 (최대 9개)")

    # ✅ 다음 버튼
    if 3 <= count <= 9:
        if st.button("다음 단계로 →", type="primary"):
            st.session_state.selected_menus = {i: [] for i in st.session_state.selected_ingredients}
            st.session_state.step = "menus"
            st.rerun()
    else:
        st.button("다음 단계로 →", disabled=True)

# ✅ 3단계: 메뉴 선택
def show_menus():
    st.subheader("🍽️ 메뉴 선택")
    st.info("각 수산물마다 최소 1개 이상 선택해주세요.")

    all_valid = True
    for ing in st.session_state.selected_ingredients:
        st.markdown(f"<div class='category-title'>🐟 {ing} 메뉴</div>", unsafe_allow_html=True)
        menus = MENU_DATA.get(ing, [])
        st.markdown("<div class='menu-grid'>", unsafe_allow_html=True)

        for menu in menus:
            jpg = os.path.join(MENU_IMAGE_PATH, f"{menu}.jpg")
            png = os.path.join(MENU_IMAGE_PATH, f"{menu}.png")
            img = load_img(jpg) or load_img(png)
            selected = menu in st.session_state.selected_menus[ing]

            if st.button(f"선택_{ing}_{menu}", key=f"menu_btn_{ing}_{menu}"):
                if selected:
                    st.session_state.selected_menus[ing].remove(menu)
                else:
                    st.session_state.selected_menus[ing].append(menu)
                st.rerun()
                
            st.markdown(render_card(menu, img, selected), unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        if len(st.session_state.selected_menus[ing]) == 0:
            all_valid = False
            st.warning(f"⚠️ {ing} 메뉴 최소 1개 선택 필요")
        else:
            st.success(f"✅ {ing}: {len(st.session_state.selected_menus[ing])}개 선택됨")

    # ✅ 버튼
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← 이전 단계"):
            st.session_state.step = "ingredients"
            st.rerun()
    with col2:
        if all_valid:
            if st.button("설문 완료하기", type="primary"):
                st.session_state.step = "complete"
                st.rerun()
        else:
            st.button("설문 완료하기", disabled=True)

# ✅ 4단계: 완료 페이지
def show_complete():
    st.balloons()
    st.success("🎉 설문이 완료되었습니다. 참여해주셔서 감사합니다!")

    # 결과 요약
    st.write("### ✅ 선택된 수산물")
    st.write(", ".join(st.session_state.selected_ingredients))

    st.write("### ✅ 선택된 메뉴")
    for ing, menus in st.session_state.selected_menus.items():
        st.write(f"- {ing}: {', '.join(menus)}")

    if st.button("🔄 새 설문 시작하기"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ✅ 페이지 라우팅
if st.session_state.step == "info":
    show_info()
elif st.session_state.step == "ingredients":
    show_ingredients()
elif st.session_state.step == "menus":
    show_menus()
else:
    show_complete()
