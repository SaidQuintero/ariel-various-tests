import streamlit as st
from chat_retriever import get_answer_azure, get_answer_pinecone

if "answer_azure" not in st.session_state:
    st.session_state.answer_azure = ""
    st.session_state.sources_azure = ""


def on_click_handler_azure():
    response = get_answer_azure(user_input_azure)
    st.session_state.answer_azure = response["content"]
    st.session_state.sources_azure = response["sources"]


st.title("💠 Ariel Azure")
user_input_azure = st.text_area("Tu pregunta ...", key="user_input_azure")
st.button("Enviar", on_click=on_click_handler_azure, key="send_azure")
st.write(st.session_state.answer_azure)
st.write(st.session_state.sources_azure)
# st.expander("Fuentas", expanded=False, *, icon=None)

st.divider()

if "answer_pinecone" not in st.session_state:
    st.session_state.answer_pinecone = ""
    st.session_state.sources_pinecone = ""


def on_click_handler_pinecone():
    response = get_answer_pinecone(user_input_pinecone)
    st.session_state.answer_pinecone = response["content"]
    st.session_state.sources_pinecone = response["sources"]


st.title("🍍 Ariel Pinecone")
user_input_pinecone = st.text_area("Tu pregunta ...", key="user_input_pinecone")
st.button("Enviar", on_click=on_click_handler_pinecone, key="send_pinecone")
st.write(st.session_state.answer_pinecone)
st.write(st.session_state.sources_pinecone)


# Qué dice el artículo del 103 del código penal? ("Cuándo se consuma el hurto" "Ley 599 de 2000")
# ¿Cuándo se consuma el hurto? ("Artículo 103 Código Penal Colombia")
# ¿Las personas jurídicas pueden ser sujetos pasivos de los delitos de injuria y calumnia? ("Personas jurídicas sujetos pasivos delitos injuria calumnia")
# ¿Cuál es el término que tiene la Fiscalía para formular acusación? ("Término Fiscalía para formular acusación" "Ley 906 de 2004") ("Término para formular acusación" "Fiscalía" "Ley 906 de 2004")
