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
MENU_DATA = {
    "맛살": ["게맛살볶음밥", "맛살전"],
    "김": ["김밥", "김무침"],
    "오징어": ["오징어볶음", "오징어초무침"]
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
