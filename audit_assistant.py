import os
import shutil
import streamlit as st
import PyPDF2

from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain.text_splitter import CharacterTextSplitter
from langchain.memory import ConversationBufferMemory

from gdrive_utils import authenticate_gdrive, upload_faiss_to_drive, download_faiss_from_drive

# 🔐 API Key
if "OPENAI_API_KEY" not in st.secrets:
    st.error("Please set your OpenAI API key in .streamlit/secrets.toml")
    st.stop()

openai_api_key = st.secrets["OPENAI_API_KEY"]

# 🤖 LLM Setup
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0,
    api_key=openai_api_key,
    streaming=True
)

# 🧠 Memory
memory = ConversationBufferMemory(return_messages=True, memory_key="chat_history")

# 📂 Constants
DB_DIR = "vector_store"
DRIVE_FILE_NAME = "faiss_vector_store.zip"

# 📄 PDF Text Extractor
def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    return "\n".join(page.extract_text() for page in reader.pages if page.extract_text())

# 🔍 Text Split & Embedding
text_splitter = CharacterTextSplitter(separator="\n", chunk_size=2000, chunk_overlap=200, length_function=len)
embeddings = HuggingFaceEmbeddings()

# 🔄 Load or Create FAISS
def load_or_create_faiss(chunks):
    drive = authenticate_gdrive()

    if download_faiss_from_drive(drive, file_title=DRIVE_FILE_NAME, dest_dir=DB_DIR):
        st.success("✅ FAISS DB loaded from Google Drive.")
        return FAISS.load_local(DB_DIR, embeddings)
    else:
        st.warning("🧠 No existing DB found, creating one.")
        if os.path.exists(DB_DIR): shutil.rmtree(DB_DIR)
        db = FAISS.from_texts(chunks, embeddings)
        db.save_local(DB_DIR)
        upload_faiss_to_drive(DB_DIR, drive, file_name=DRIVE_FILE_NAME)
        st.success("✅ New FAISS DB created and uploaded to Drive.")
        return db

# 🌐 Streamlit UI
st.title("🕵️ AI Audit Assistant")
st.markdown("Upload a PDF document and ask audit questions based on it.")

uploaded_file = st.file_uploader("📎 Upload Audit PDF", type="pdf")

if uploaded_file:
    pdf_text = extract_text_from_pdf(uploaded_file)
    st.success("📖 Document processed!")

    chunks = text_splitter.split_text(pdf_text)
    db = load_or_create_faiss(chunks)

    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 4})

    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory
    )

    user_question = st.text_input("💬 Ask a question about the audit document:")

    if user_question:
        with st.spinner("Thinking like a real auditor..."):
            try:
                answer = qa_chain.run(user_question)
                st.text_area("📘 Audit Assistant Answer", value=answer, height=200)
            except Exception as e:
                st.error(f"Error: {e}")
