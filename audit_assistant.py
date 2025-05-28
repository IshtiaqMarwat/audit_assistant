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

# 🔐 Load your OpenAI API key from Streamlit secrets or environment variable
openai_api_key = st.secrets["OPENAI_API_KEY"] if "OPENAI_API_KEY" in st.secrets else os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    st.error("🔐 Please set your OpenAI API key in .streamlit/secrets.toml or as an environment variable.")
    st.stop()

# 📁 FAISS DB path (Google Drive mounted path)
DB_DIR = "vector_store"  # Change this if needed

# 🧠 LLM Setup
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, api_key=openai_api_key)
memory = ConversationBufferMemory(return_messages=True, memory_key="chat_history")
text_splitter = CharacterTextSplitter(separator="\n", chunk_size=2000, chunk_overlap=200, length_function=len)
embeddings = HuggingFaceEmbeddings()

retriever = None
qa_chain = None

# 📄 Extract text from PDF
def extract_text_from_pdf(file):
    try:
        reader = PyPDF2.PdfReader(file)
        return "\n".join(page.extract_text() or '' for page in reader.pages)
    except Exception as e:
        raise ValueError(f"PDF read error: {str(e)}")

# 🔁 Create or update FAISS DB
def setup_db_from_pdf(pdf):
    global retriever, qa_chain
    try:
        text = extract_text_from_pdf(pdf)
        chunks = text_splitter.split_text(text)
        new_db = FAISS.from_texts(chunks, embeddings)

        if os.path.exists(DB_DIR):
            existing_db = FAISS.load_local(DB_DIR, embeddings, allow_dangerous_deserialization=True)
            existing_db.merge_from(new_db)
            db = existing_db
            status = "📚 Merged new PDF into existing FAISS DB."
        else:
            db = new_db
            status = "🆕 Created new FAISS DB."

        db.save_local(DB_DIR)
        retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 4})
        qa_chain = ConversationalRetrievalChain.from_llm(llm=llm, retriever=retriever, memory=memory)

        return status
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ❓ Question handler
def ask_question(question):
    global retriever, qa_chain
    if qa_chain is None:
        if os.path.exists(DB_DIR):
            try:
                db = FAISS.load_local(DB_DIR, embeddings, allow_dangerous_deserialization=True)
                retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 4})
                qa_chain = ConversationalRetrievalChain.from_llm(llm=llm, retriever=retriever, memory=memory)
            except Exception as e:
                return f"❌ Failed to load FAISS DB: {str(e)}"
        else:
            return "⚠️ Please upload a PDF first."

    try:
        return qa_chain.run(question)
    except Exception as e:
        return f"❌ Error: {str(e)}"

# 🌐 Streamlit UI
st.set_page_config(page_title="AI Audit Assistant", page_icon="🕵️")
st.title("🕵️ AI Audit Assistant")
st.markdown("Upload multiple audit-related PDFs and ask document-aware questions.")

uploaded_file = st.file_uploader("📎 Upload Audit PDF", type="pdf")

if uploaded_file:
    status = setup_db_from_pdf(uploaded_file)
    st.success(status)

user_question = st.text_input("💬 Ask a question about your documents:")

if user_question:
    with st.spinner("Thinking like an auditor..."):
        answer = ask_question(user_question)
        st.text_area("📘 Answer", value=answer, height=250)
