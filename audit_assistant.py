import os
import streamlit as st
import PyPDF2
import shutil

from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain

from drive_utils import upload_faiss_to_drive, download_faiss_from_drive

# 📂 Constants
TEMP_DIR = "temp_faiss"
DB_ZIP = "faiss_vector_store.zip"

# 🔐 Load API key
openai_api_key = st.secrets["OPENAI_API_KEY"]

# ⚙️ LangChain setup
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, api_key=openai_api_key)
embeddings = HuggingFaceEmbeddings()
text_splitter = CharacterTextSplitter(separator="\n", chunk_size=2000, chunk_overlap=200)
memory = ConversationBufferMemory(return_messages=True, memory_key="chat_history")

retriever = None
qa_chain = None

# 📄 Extract text from PDF
def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    return "\n".join(page.extract_text() or '' for page in reader.pages)

# 🔁 Update and upload FAISS DB
def update_faiss_from_pdf(pdf):
    try:
        text = extract_text_from_pdf(pdf)
        chunks = text_splitter.split_text(text)
        new_db = FAISS.from_texts(chunks, embeddings)

        if download_faiss_from_drive(DB_ZIP, TEMP_DIR):
            existing_db = FAISS.load_local(TEMP_DIR, embeddings, allow_dangerous_deserialization=True)
            existing_db.merge_from(new_db)
            db = existing_db
            status = "📚 Merged new content into existing FAISS DB."
        else:
            db = new_db
            status = "🆕 Created new FAISS DB."

        db.save_local(TEMP_DIR)
        upload_faiss_to_drive(TEMP_DIR)
        shutil.rmtree(TEMP_DIR)

        return f"{status} ✅ FAISS DB uploaded to Google Drive."
    except Exception as e:
        return f"❌ Error updating FAISS DB: {e}"

# ❓ Ask question from FAISS DB
def query_faiss(question):
    global retriever, qa_chain
    try:
        if not download_faiss_from_drive(DB_ZIP, TEMP_DIR):
            return "⚠️ FAISS DB not found in Google Drive. Please upload a PDF first."

        db = FAISS.load_local(TEMP_DIR, embeddings, allow_dangerous_deserialization=True)
        retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 4})
        qa_chain = ConversationalRetrievalChain.from_llm(llm=llm, retriever=retriever, memory=memory)
        shutil.rmtree(TEMP_DIR)

        return qa_chain.run(question)
    except Exception as e:
        return f"❌ Error: {e}"

# 🌐 Streamlit UI
st.set_page_config(page_title="AI Audit Assistant", page_icon="🕵️")
st.title("🕵️ AI Audit Assistant")

uploaded = st.file_uploader("📎 Upload a PDF file", type="pdf")
if uploaded:
    with st.spinner("📂 Processing..."):
        st.success(update_faiss_from_pdf(uploaded))

question = st.text_input("💬 Ask a question about your documents:")
if question:
    with st.spinner("🔍 Thinking like an auditor..."):
        answer = query_faiss(question)
        st.text_area("📘 Audit Assistant Answer", value=answer, height=250)
