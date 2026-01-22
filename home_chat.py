"""
Home Chat Module with Function Calling and File Upload
Provides a clean chat interface with web search capability and image upload support
"""

import streamlit as st
import json
import base64
from web_search import perform_web_search

def render_home_chat(chat_manager):
    """
    Render the home chat interface with function calling support
    
    Args:
        chat_manager: ChatManager instance for API calls
    """
    
    # Initialize Chat History for Home
    if "home_chat_messages" not in st.session_state:
        st.session_state.home_chat_messages = []

    # Custom CSS for Gemini-like UI & Centering
    center_css = ""
    if not st.session_state.home_chat_messages:
        center_css = """
<style>
/* Move the bottom chat input container to the middle */
[data-testid="stBottom"] {
    bottom: 40vh !important;
    transition: bottom 0.3s ease-in-out;
    background: transparent !important;
    z-index: 1000 !important;
}
/* Hide the default footer decoration if visible */
footer {display: none !important;}
</style>
"""
    
    st.markdown(f"""
    <style>
    /* Greeting Styles */
    .greeting-container {{
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        padding-top: 10vh;
        padding-bottom: 2rem;
        text-align: center;
    }}
    .greeting-title {{
        font-size: 3rem;
        font-weight: 700;
        background: -webkit-linear-gradient(45deg, #4285F4, #9B72CB, #D96570);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        white-space: nowrap;
    }}
    .greeting-subtitle {{
        font-size: 2rem;
        font-weight: 600;
        color: #5f6368;
    }}
    @media (prefers-color-scheme: dark) {{
        .greeting-subtitle {{
            color: #bdc1c6;
        }}
    }}
    
    /* Chat Message Styles */
    .stChatMessage {{
        background-color: transparent !important;
    }}
    </style>
    {center_css}
    """, unsafe_allow_html=True)

    # Greeting Section (Only show if chat is empty)
    if not st.session_state.home_chat_messages:
        user_info = st.session_state.get('user_info', {})
        user_name = user_info.get('name', '사우')
        
        st.markdown('<div class="greeting-container">', unsafe_allow_html=True)
        st.markdown(f'<div class="greeting-title">{user_name}님 안녕하세요</div>', unsafe_allow_html=True)
        st.markdown('<div class="greeting-subtitle">무엇을 도와드릴까요?</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Display Chat History
    for message in st.session_state.home_chat_messages:
        with st.chat_message(message["role"]):
            # Handle both simple string content and list content (multimodal)
            if isinstance(message["content"], list):
                for item in message["content"]:
                    if item["type"] == "text":
                        st.markdown(item["text"])
                    elif item["type"] == "image_url":
                        st.image(item["image_url"]["url"], width=300)
            else:
                st.markdown(message["content"])

    # File Upload Section (above chat input)
    if "home_uploader_key" not in st.session_state:
        st.session_state.home_uploader_key = 0
    
    uploaded_file = st.file_uploader(
        "Drag and drop files here",
        type=['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'tif'],
        key=f"home_upload_{st.session_state.home_uploader_key}",
        help="Limit 200MB per file • PDF, PNG, JPG, JPEG, TIFF, BMP, TIF"
    )
    
    if uploaded_file:
        st.success(f"✅ 첨부됨: {uploaded_file.name}")

    # Chat Input Area
    if prompt := st.chat_input("GPT 5.2에게 물어보기"):
        # Prepare content for user message
        user_content = [{"type": "text", "text": prompt}]
        
        # Handle Uploaded File (Image)
        if uploaded_file and uploaded_file.type.startswith('image/'):
            image_bytes = uploaded_file.getvalue()
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            image_data = f"data:{uploaded_file.type};base64,{base64_image}"
            user_content.append({
                "type": "image_url",
                "image_url": {"url": image_data}
            })
        
        # Handle Text/PDF File (Context Injection)
        elif uploaded_file:
            try:
                if uploaded_file.type == "text/plain":
                    text_content = uploaded_file.getvalue().decode("utf-8")
                    user_content[0]["text"] += f"\n\n[첨부 파일 내용 ({uploaded_file.name})]:\n{text_content}"
                elif uploaded_file.type == "application/pdf":
                    user_content[0]["text"] += f"\n\n[첨부 파일 ({uploaded_file.name})이 전송되었습니다. PDF는 현재 화면 출력이 제한적일 수 있습니다.]"
                else:
                    user_content[0]["text"] += f"\n\n[첨부 파일 ({uploaded_file.name})이 전송되었습니다.]"
            except Exception as e:
                st.error(f"파일 읽기 실패: {e}")
        
        # Add user message to state
        st.session_state.home_chat_messages.append({
            "role": "user", 
            "content": user_content
        })
        
        # Display user message
        with st.chat_message("user"):
            for item in user_content:
                if item["type"] == "text":
                    st.markdown(item["text"])
                elif item["type"] == "image_url":
                    st.image(item["image_url"]["url"], width=300)
            
        # Assistant Response with Function Calling
        with st.chat_message("assistant"):
            with st.spinner("생각 중..."):
                try:
                    # Define web search function tool
                    tools = [{
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "description": "인터넷에서 최신 정보를 검색합니다. 실시간 정보, 뉴스, 최신 데이터가 필요할 때 사용하세요.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "검색할 키워드 또는 질문"
                                    }
                                },
                                "required": ["query"]
                            }
                        }
                    }]
                    
                    # Prepare messages for API
                    api_messages = []
                    for msg in st.session_state.home_chat_messages:
                        api_messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
                    
                    # Initial API call with function calling
                    response = chat_manager.client.chat.completions.create(
                        model=chat_manager.deployment_name,
                        messages=api_messages,
                        tools=tools,
                        tool_choice="auto",
                        max_completion_tokens=4096,
                        temperature=0.7
                    )
                    
                    response_message = response.choices[0].message
                    
                    # Check if function call is requested
                    if response_message.tool_calls:
                        tool_call = response_message.tool_calls[0]
                        function_name = tool_call.function.name
                        
                        if function_name == "web_search":
                            function_args = json.loads(tool_call.function.arguments)
                            search_query = function_args.get("query")
                            
                            # Display search indication
                            st.info(f"🔍 웹 검색 중: {search_query}")
                            
                            # Perform web search
                            search_results = perform_web_search(search_query)
                            
                            # Add assistant's tool call to messages
                            api_messages.append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [{
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": function_name,
                                        "arguments": tool_call.function.arguments
                                    }
                                }]
                            })
                            
                            # Add tool response to messages
                            api_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": search_results
                            })
                            
                            # Get final response with search results
                            final_response = chat_manager.client.chat.completions.create(
                                model=chat_manager.deployment_name,
                                messages=api_messages,
                                max_completion_tokens=4096,
                                temperature=0.7
                            )
                            
                            response_text = final_response.choices[0].message.content
                    else:
                        # No function call, use direct response
                        response_text = response_message.content
                    
                    # Display response
                    st.markdown(response_text)
                    
                    # Save to history
                    st.session_state.home_chat_messages.append({
                        "role": "assistant",
                        "content": response_text
                    })
                    
                    # Clear uploaded file by incrementing key
                    if uploaded_file:
                        st.session_state.home_uploader_key += 1
                    
                    # Rerun to update UI
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"오류가 발생했습니다: {e}")
                    import traceback
                    st.error(traceback.format_exc())
