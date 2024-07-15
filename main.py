import streamlit as st
from chat_retriever import get_answer_azure, get_answer_pinecone

if 'answer_azure' not in st.session_state:
    st.session_state.answer_azure = ""

def on_click_handler_azure():
    st.session_state.answer_azure = get_answer_azure(st.session_state.user_input_azure)
    
st.title("💠 Ariel Azure")
user_input = st.text_area("Tu pregunta ...", key='user_input_azure')
st.button("Enviar", on_click=on_click_handler_azure, key="send_azure")
st.write(st.session_state.answer_azure)

st.divider()

if 'answer_pinecone' not in st.session_state:
    st.session_state.answer_pinecone = ""

def on_click_handler_pinecone():
    st.session_state.answer_pinecone = get_answer_pinecone(st.session_state.user_input_pinecone)
    
st.title("🍍 Ariel Pinecone")
user_input = st.text_area("Tu pregunta ...", key='user_input_pinecone')
st.button("Enviar", on_click=on_click_handler_pinecone, key="send_pinecone")
st.write(st.session_state.answer_pinecone)