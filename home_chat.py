"""
Home Chat Module with Function Calling and File Upload
Provides a clean chat interface with web search capability and image upload support
"""

import streamlit as st
import json
import base64
import os
import uuid
from datetime import datetime
from web_search import perform_web_search

# --- History Management ---
HISTORY_FILE = "chat_history.json"

def load_history():
    """Load chat history from local JSON file."""
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading history: {e}")
        return {}

def save_history(history):
    """Save chat history to local JSON file."""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")

def get_session_title(messages):
    """Generate a title for the session based on the first user message."""
    for msg in messages:
        if msg["role"] == "user":
            content = msg["content"]
            if isinstance(content, list):
                for item in content:
                    if item["type"] == "text":
                        return item["text"][:20] + "..."
            else:
                return str(content)[:20] + "..."
    return "새로운 대화"

def render_home_chat(chat_manager):
    """
    Render the home chat interface with function calling support and right sidebar history
    
    Args:
        chat_manager: ChatManager instance for API calls
    """
    
    # Initialize Session State for History
    if "chat_history_data" not in st.session_state:
        st.session_state.chat_history_data = load_history()
    
    if "current_session_id" not in st.session_state:
        # Create a new session if none exists
        new_id = str(uuid.uuid4())
        st.session_state.current_session_id = new_id
        st.session_state.chat_history_data[new_id] = {
            "title": "새로운 대화",
            "timestamp": datetime.now().isoformat(),
            "messages": []
        }
        st.session_state.home_chat_messages = []

    # Sync current session messages with home_chat_messages
    # This ensures that if we switched sessions, home_chat_messages is updated
    # But we also need to ensure that if we add messages, they are saved back.
    # We'll do the save on message send.
    
    # Layout: Spacer L (25%) | Main Chat (50%) | Spacer R (10%) | History Sidebar (15%)
    # This perfectly centers the chat (0.25 + 0.5/2 = 0.5) and keeps sidebar on right
    col_spacer_l, col_chat, col_spacer_r, col_history = st.columns([0.25, 0.5, 0.1, 0.15])
    
    # Custom CSS for Sidebar Styling
    st.markdown("""
    <style>
    /* Target the fourth column (History Sidebar) */
    [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-of-type(4) {
        background-color: #1E1E1E; /* Darker background for sidebar */
        border-left: 1px solid #333;
        padding: 1rem;
        border-radius: 10px;
    }
    /* Adjust button styles in sidebar */
    [data-testid="column"]:nth-of-type(4) button {
        text-align: left;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # --- Right Sidebar (History) ---
    with col_history:
        st.markdown("### 채팅 기록")
        
        # New Chat Button
        if st.button("➕ 새 채팅", use_container_width=True):
            new_id = str(uuid.uuid4())
            st.session_state.current_session_id = new_id
            st.session_state.chat_history_data[new_id] = {
                "title": "새로운 대화",
                "timestamp": datetime.now().isoformat(),
                "messages": []
            }
            st.session_state.home_chat_messages = []
            st.rerun()
            
        st.markdown("---")
        
        # Sort sessions by timestamp (newest first)
        sorted_sessions = sorted(
            st.session_state.chat_history_data.items(),
            key=lambda x: x[1].get("timestamp", ""),
            reverse=True
        )
        
        # Display History Items
        for session_id, session_data in sorted_sessions:
            title = session_data.get("title", "대화")
            # Highlight current session
            if session_id == st.session_state.current_session_id:
                if st.button(f"📂 {title}", key=f"hist_{session_id}", use_container_width=True, type="primary"):
                    pass # Already selected
            else:
                if st.button(f"📄 {title}", key=f"hist_{session_id}", use_container_width=True):
                    st.session_state.current_session_id = session_id
                    st.session_state.home_chat_messages = session_data.get("messages", [])
                    st.rerun()
        
        # Delete All Button (Optional, for cleanup)
        if st.button("🗑️ 기록 삭제", use_container_width=True):
            st.session_state.chat_history_data = {}
            save_history({})
            # Reset current
            new_id = str(uuid.uuid4())
            st.session_state.current_session_id = new_id
            st.session_state.chat_history_data[new_id] = {
                "title": "새로운 대화",
                "timestamp": datetime.now().isoformat(),
                "messages": []
            }
            st.session_state.home_chat_messages = []
            st.rerun()

    # --- Main Chat Area (Left) ---
    with col_chat:
        # Custom CSS for Gemini-like UI & Centering
        center_css = ""
        if not st.session_state.home_chat_messages:
            center_css = """
    <style>
    /* Make the chat input relative so it sits right below the content */
    [data-testid="stBottom"] {
        position: relative !important;
        bottom: auto !important;
        background: transparent !important;
        padding-top: 2rem;
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

        # Chat Input Area
        if prompt := st.chat_input("GPT 5.2에게 물어보기"):
            # Prepare content for user message
            user_content = [{"type": "text", "text": prompt}]
            
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
                        
                        # --- Auto-Save to Local Storage ---
                        current_id = st.session_state.current_session_id
                        
                        # Update title if it's "새로운 대화" and we have messages
                        current_title = st.session_state.chat_history_data[current_id]["title"]
                        if current_title == "새로운 대화" and len(st.session_state.home_chat_messages) > 0:
                            new_title = get_session_title(st.session_state.home_chat_messages)
                            st.session_state.chat_history_data[current_id]["title"] = new_title
                        
                        # Update messages and timestamp
                        st.session_state.chat_history_data[current_id]["messages"] = st.session_state.home_chat_messages
                        st.session_state.chat_history_data[current_id]["timestamp"] = datetime.now().isoformat()
                        
                        # Save to file
                        save_history(st.session_state.chat_history_data)
                        
                        # Rerun to update UI (Sidebar title, etc.)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"오류가 발생했습니다: {e}")
                        import traceback
                        st.error(traceback.format_exc())
