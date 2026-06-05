import streamlit as st
import json
import os
from datetime import datetime
from PIL import Image
from openai import OpenAI

# 1. OpenAI 클라이언트 초기화
# 환경 변수에 OPENAI_API_KEY가 등록되어 있어야 합니다.
try:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
except Exception as e:
    st.error("OpenAI API Key가 설정되지 않았거나 올바르지 않습니다. 환경 변수를 확인해주세요.")

# 2. 초기 세션 상태(Session State) 설정 (Tech Spec 7번 반영)
if "items" not in st.session_state:
    st.session_state.items = []

# 3. 주요 함수 설계 (Tech Spec 5번 반영)
def extract_items_from_receipt(image_file):
    """
    OpenAI GPT-4o(Vision)를 활용하여 영수증 이미지에서 
    개인정보를 제외한 구매일과 재료(아이템) 목록을 JSON 형태로 추출합니다.
    """
    # Streamlit 업로드 파일을 바이너리로 읽기
    bytes_data = image_file.read()
    
    # OpenAI Structured Outputs를 유도하기 위한 시스템 프롬프트
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
        # GPT-4o 모델을 사용하여 이미지 분석 요청
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_file.getvalue().hex()}", # 간단한 hex/base64 변환 처리
                                "url": f"data:image/jpeg;base64,{st.image_to_base64(bytes_data)}" if hasattr(st, 'image_to_base64') else ""
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
        )
        
        # 실제 환경에서는 base64 인코딩 표준 함수를 쓰는 것이 안전하므로 내장 라이브러리로 대체 가이드
        import base64
        base64_image = base64.b64encode(bytes_data).decode('utf-8')
        
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
            response_format={"type": "json_object"} # JSON 결과 강제 변환 옵션
        )
        
        result_json = json.loads(response.choices[0].message.content)
        return result_json
        
    except Exception as e:
        st.error(f"AI 인식 중 오류가 발생했습니다: {e}")
        return None

def add_items(extracted_data):
    """
    추출된 데이터를 Tech Spec 4번의 데이터 모델 형식에 맞추어 
    st.session_state.items에 저장합니다.
    """
    purchase_date = extracted_data.get("purchase_date", datetime.today().strftime('%Y-%m-%d'))
    new_items_names = extracted_data.get("items", [])
    
    for name in new_items_names:
        # Tech Spec 4. 데이터 모델 구조 정의
        # (dDay와 expire_date는 추후 유통기한 산출 함수인 shelf_life()에서 처리하도록 임시 초기화)
        item_model = {
            "name": name,
            "dDay": 0, 
            "purchase_date": purchase_date,
            "expire_date": "" 
        }
        st.session_state.items.append(item_model)


# 4. UI 컴포넌트 구성 (Tech Spec 6번 메인 페이지 반영)
st.title("Keep And Cook 🍳")
st.subheader("영수증 재료 등록 (KAC-001)")
st.write("2030 자취생을 위한 냉장고 유통기한 관리 서비스")

# 파일 업로더 생성
uploaded_file = st.file_uploader("영수증 이미지를 첨부해주세요.", type=["jpg", "png"])

if uploaded_file is not None:
    # 업로드된 이미지 화면에 미리보기 출력
    image = Image.open(uploaded_file)
    st.image(image, caption='업로드된 영수증', use_column_width=True)
    
    # 인식 시작 버튼
    if st.button("영수증에서 재료 추출하기"):
        with st.spinner("AI가 영수증에서 재료와 구매일을 추출하고 있습니다 (개인정보 마스킹 포함)..."):
            extracted_data = extract_items_from_receipt(uploaded_file)
            
            if extracted_data:
                st.success("추출 완료!")
                st.write(f"**🗓️ 인식된 구매일:** {extracted_data.get('purchase_date')}")
                st.write(f"**🛒 추출된 재료:** {', '.join(extracted_data.get('items', []))}")
                
                # 세션 상태에 추가
                add_items(extracted_data)
                st.toast("모든 재료가 성공적으로 저장소에 추가되었습니다!")

---
# 5. 저장 데이터 확인 (디버깅 및 추후 통합용 페이지 컴포넌트 예시)
st.markdown("---")
st.subheader("📦 현재 세션 저장소 상태 (st.session_state.items)")
if st.session_state.items:
    st.json(st.session_state.items)
else:
    st.info("아직 저장된 재료가 없습니다. 영수증을 업로드하여 재료를 추가해보세요.")
