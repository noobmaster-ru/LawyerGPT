try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import streamlit as st
import uuid
from datetime import datetime
import pickle
import os
import json

from rag_agent import RagAgent
from database.history_base import HistoryBase
from src.logging_conf import logger
from src.config import Config


settings = Config.from_yaml("config.yaml")


# Настройка страницы
st.set_page_config(
    page_title="LawerGPT",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)


def save_settings():
    with open('settings.json', 'w') as f:
        json.dump(st.session_state.settings, f)


def load_settings():
    if os.path.exists('settings.json'):
        with open('settings.json', 'r') as f:
            return json.load(f)
    return settings.rag_settings.copy()

def update_settings():
    """Обновляет настройки из виджетов и пересоздает агента при необходимости"""
    old_settings = st.session_state.settings.copy()
    
    # Обновляем настройки из виджетов
    for key in settings.rag_settings.keys():
        if key in st.session_state:
            st.session_state.settings[key] = st.session_state[key]
    
    # Проверяем изменения и обновляем агента
    if old_settings != st.session_state.settings:
        st.session_state.rag_agent.set_settings(**st.session_state.settings)
        logger.info(f"Settings updated: {st.session_state.settings}")

def dump_chats():
    with open('chats.pl', 'wb') as f:
        pickle.dump(st.session_state.chats, f)

# Функции для работы с чатами
def create_new_chat():
    chat_id = str(uuid.uuid4())
    logger.info("NEW CHAT: %s" % (chat_id,))
    st.session_state.chats[chat_id] = {
        'id': chat_id,
        'name': f"Чат {len(st.session_state.chats) + 1}",
        'created_at': datetime.now(),
        'messages': []
    }
    st.session_state.chat_id = chat_id
    st.session_state.settings['chat_id'] = chat_id
    dump_chats()

def delete_chat(chat_id):
    if chat_id in st.session_state.chats:
        if st.session_state.current_chat_id != chat_id:
            del st.session_state.chats[chat_id]
            st.session_state.history_db.delete_messages_by_chat_id(chat_id)
            dump_chats()

def clear_chat_history():
    cid = st.session_state.current_chat_id
    if cid:
        st.session_state.chats[cid]['messages'] = []
        st.session_state.history_db.delete_messages_by_chat_id(chat_id)


# Инициализация session state
if 'user_input' not in st.session_state:
    st.session_state['user_input'] = ""
if 'settings' not in st.session_state:
    st.session_state.settings = load_settings()
if 'chats' not in st.session_state:
    if os.path.exists('chats.pl'):
        with open('chats.pl', 'rb') as f:
            st.session_state.chats = pickle.load(f)
    else:
        st.session_state.chats = {}
        create_new_chat()
if 'current_chat_id' not in st.session_state:
    st.session_state.current_chat_id = None
if 'rag_agent' not in st.session_state:
    st.session_state.rag_agent = RagAgent(**st.session_state.settings)

if 'history_db' not in st.session_state:
    st.session_state.history_db = HistoryBase()

# Стили CSS
st.markdown("""
<style>
.chat-row { display: flex; width: 100%; margin-bottom: 0.5rem; }
.chat-row.user { justify-content: flex-end; }
.chat-row.agent { justify-content: flex-start; }
.chat-bubble {
    max-width: 70%;
    padding: 0.75rem 1rem;
    border-radius: 1rem;
    position: relative;
    line-height: 1.4;
}
.chat-bubble.user {
    background-color: #acf;
    color: #000;
    border-bottom-right-radius: 0;
}
.chat-bubble.agent {
    background-color: #eee;
    color: #000;
    border-bottom-left-radius: 0;
}
textarea.custom-textarea {
    /* Дополнительные стили для textarea, если нужно */
}
</style>
""", unsafe_allow_html=True)

# Функция обработки ввода
def process_input():
    q = st.session_state['user_input'].strip()
    if q:
        current_chat = st.session_state.chats.get(st.session_state.current_chat_id)
        if current_chat:
            current_chat['messages'].append({
                'role': 'user',
                'content': q,
                'timestamp': datetime.now()
            })
            with st.spinner("Ищем ответ..."):
                resp = st.session_state.rag_agent(q)
            current_chat['messages'].append({
                'role': 'assistant',
                'content': resp['answer'],
                'contexts': resp['contexts'],
                'timestamp': datetime.now()
            })
            st.session_state['user_input'] = ""

# Левая боковая панель
with st.sidebar:
    if st.button("➕ Новый чат", use_container_width=True):
        create_new_chat()
        st.rerun()

    st.markdown("---")
    for chat_id, chat in st.session_state.chats.items():
        cols = st.columns([8, 1])
        with cols[0]:
            if st.button(chat['name'],
                         key=f"chat_{chat_id}",
                         use_container_width=True,
                         type="primary" if chat_id == st.session_state.current_chat_id else "secondary"):
                st.session_state.current_chat_id = chat_id
                st.rerun()
        with cols[1]:
            if st.button("🗑️", key=f"del_{chat_id}", use_container_width=True):
                delete_chat(chat_id)
                st.rerun()

# Основная область и панель настроек
col_main, col_settings = st.columns([3, 1])

with col_main:
    st.markdown("## ⚖️ LawerGPT")

    if not st.session_state.current_chat_id:
        if not st.session_state.chats:
            create_new_chat()
        else:
            st.session_state.current_chat_id = next(iter(st.session_state.chats))

    current_chat = st.session_state.chats.get(st.session_state.current_chat_id)

    if current_chat:
        if st.button("🧹 Очистить диалог", use_container_width=True):
            clear_chat_history()

        for msg in current_chat['messages']:
            role = msg['role']
            content = msg['content']
            row_cls = "chat-row user" if role == "user" else "chat-row agent"
            bub_cls = "chat-bubble user" if role == "user" else "chat-bubble agent"
            st.markdown(f"""
<div class="{row_cls}">
    <div class="{bub_cls}">
        {content}
    </div>
</div>
""", unsafe_allow_html=True)

            if role == 'assistant' and 'contexts' in msg:
                for ctx in msg['contexts']:
                    if ctx:  # Проверяем, что контекст не пустой
                        with st.expander(f"{ctx['title']}"):
                            st.markdown(ctx['text'])

    st.text_area("Ваш вопрос:", height=100, key="user_input", help="Нажмите Ctrl+Enter для отправки")
    st.button("Отправить", on_click=process_input, use_container_width=True, key="submit_button")

    st.markdown("""
<script>
document.addEventListener('DOMContentLoaded', function() {
    const textarea = document.querySelector('textarea');
    const submitButton = document.querySelector('button[data-testid="stButton"][id*="submit_button"]');
    if (textarea && submitButton) {
        textarea.addEventListener('keydown', function(event) {
            if (event.ctrlKey && event.key === 'Enter') {
                event.preventDefault();
                submitButton.click();
            }
        });
    }
});
</script>
""", unsafe_allow_html=True)

with col_settings:
    st.markdown("### ⚙️ Настройки")

    with st.expander("Основные параметры", expanded=True):
        mode = st.radio(
            "Режим работы:",
            options=['fast', 'standard', 'deep'],
            format_func=lambda x: {
                'fast': '⚡ Быстрый',
                'standard': '⚖️ Стандартный',
                'deep': '🧠 Глубокий'
            }[x],
            index=['fast', 'standard', 'deep'].index(st.session_state.settings['mode']),
            horizontal=True,
            key="mode",
            on_change=update_settings,
        )
        if mode != st.session_state.settings['mode']:
            st.session_state.settings['mode'] = mode
            st.rerun()

    with st.expander("Настройки разработчика", expanded=False):
        st.slider("Температура ответа",
                      0.0, 1.0, st.session_state.settings['answer_temperature'], step=0.1,
                      key="answer_temperature",
                      on_change=update_settings)
        st.checkbox("Включить роутер",
                    value=st.session_state.settings['router_enable'],
                    key="router_enable",
                    on_change=update_settings
                    )
        if st.session_state.settings['router_enable']:
            st.slider("Температура роутера",
                      0.0, 1.0, st.session_state.settings['router_temperature'], step=0.1,
                      key="router_temperature",
                      on_change=update_settings)

        st.markdown("---")
        st.checkbox("Включить БД",
                    value=st.session_state.settings['db_enable'],
                    key="db_enable",
                    on_change=update_settings)
        if st.session_state.settings['db_enable']:
            st.number_input("Число чанков", 1, 20,
                            st.session_state.settings['chunk_count'],
                            key="chunk_count",
                            on_change=update_settings)

        st.markdown("---")
        st.checkbox("Включить реранкер",
                    value=st.session_state.settings['reranker_enable'],
                    key="reranker_enable",
                    on_change=update_settings)
        if st.session_state.settings['reranker_enable']:
            st.slider("Температура реранкера",
                      0.0, 1.0, st.session_state.settings['reranker_temperature'], step=0.1,
                      key="reranker_temperature",
                      on_change=update_settings)

        st.markdown("---")
        st.checkbox("Chain of Thoughts", key="chain_of_thoughts", on_change=update_settings)

    if st.button("💾 Сохранить настройки", use_container_width=True):
        save_settings()
        st.success("Настройки сохранены!")



# Футер
st.markdown("---")
st.markdown(
    '<p style="text-align:center;color:#888;">Юридическая RAG система v1.0</p>',
    unsafe_allow_html=True
)