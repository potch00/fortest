import streamlit as st
import json
from datetime import datetime
from PIL import Image
from openai import OpenAI
import base64

# 초기 세션 상태(Session State) 설정
if "items" not in st.session_state:
    st.session_state.items = []

# --- 🔑 1. 사이드바에 API 키 입력창 추가 ---
st.sidebar.title("🔐 설정 (Settings)")
user_openai_api_key = st.sidebar.text_input(
    "OpenAI API Key를 입력하세요", 
    type="password",  # 입력할 때 글자가 주룩(***) 숨겨지도록 설정
    help="OpenAI 홈페이지에서 발급받은 api 키(sk-...)를 입력해야 기능이 작동합니다."
)

# 주요 함수 설계
def extract_items_from_receipt(image_file, api_key):
    """
    사용자가 입력한 API 키를 사용하여 OpenAI gpt-4o 모델로 영수증을 분석합니다.
    """
    # 2. 사용자가 입력한 키로 OpenAI 클라이언트 인스턴스 생성
    client = OpenAI(api_key=api_key)
    
    bytes_data = image_file.read()
    base64_image = base64.b64encode(bytes_data).decode('utf-8')
    
    prompt = """
    당신은 영수증에서 구매 내역을 추출하는 유용한 비서입니다.
    제공된 영수증 이미지에서 다음 정보를 찾아 정확하게 추출해주세요:
    1. 결제일/구매일 (YYYY-MM-DD 형식)
    2. 구매한 품목 중 '식재료(재료)'에 해당하는 품목명 리스트

    **주의사항**: 
    - 영수증 내의 이름, 카드번호, 주소, 전화번호 등의 '개인 정보'는 절대 포함하지 마십시오 (자동 마스킹).
    - 반환 형식은 반드시 아래의 JSON 포맷을 엄격히 따라야 하며, 마크다운(```json 등)을 제외한 순수 JSON 문자열만 반환하세요.

    {
        "purchase_date": "YYYY-MM-DD",
        "items": ["재료명1", "재료명2", ...]
    }
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )
        
        result_json = json.loads(response.choices[0].message.content)
        return result_json
        
    except Exception as e:
        st.error(f"AI 인식 중 오류가 발생했습니다: {e}")
        return None

def add_items(extracted_data):
    purchase_date = extracted_data.get("purchase_date", datetime.today().strftime('%Y-%m-%d'))
    new_items_names = extracted_data.get("items", [])
    
    for name in new_items_names:
        item_model = {
            "name": name,
            "dDay": 0, 
            "purchase_date": purchase_date,
            "expire_date": "" 
        }
        st.session_state.items.append(item_model)


# UI 컴포넌트 구성 (메인 페이지)
st.title("Keep And Cook 🍳")
st.subheader("영수증 재료 등록 (KAC-001)")
st.write("2030 자취생을 위한 냉장고 유통기한 관리 서비스")

# 파일 업로더 생성
uploaded_file = st.file_uploader("영수증 이미지를 첨부해주세요.", type=["jpg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption='업로드된 영수증', use_column_width=True)
    
    # 인식 시작 버튼
    if st.button("영수증에서 재료 추출하기"):
        
        # --- 🛡️ 3. API 키 입력 여부 검증 ---
        if not user_openai_api_key:
            st.warning("왼쪽 사이드바에 OpenAI API Key를 먼저 입력해주세요!")
        else:
            with st.spinner("AI가 영수증에서 재료와 구매일을 추출하고 있습니다..."):
                # 입력받은 API 키를 함수로 전달
                extracted_data = extract_items_from_receipt(uploaded_file, user_openai_api_key)
                
                if extracted_data:
                    st.success("추출 완료!")
                    st.write(f"**🗓️ 인식된 구매일:** {extracted_data.get('purchase_date')}")
                    st.write(f"**🛒 추출된 재료:** {', '.join(extracted_data.get('items', []))}")
                    
                    add_items(extracted_data)
                    st.toast("모든 재료가 성공적으로 저장소에 추가되었습니다!")

# 저장 데이터 확인 (디버깅용)
st.markdown("---")
st.subheader("📦 현재 세션 저장소 상태")
if st.session_state.items:
    st.json(st.session_state.items)
else:
    st.info("아직 저장된 재료가 없습니다.")
