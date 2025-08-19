import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the API key from environment variables
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

st.set_page_config(page_title="AI Chatbot App", page_icon="🤖", layout="wide")
st.title("My First AI Chatbot App")
st.write("This is a simple chatbot app using Google Gemini AI.")

# Initialize the Generative AI model
model = genai.GenerativeModel('gemini-1.5-flash')

# --- Roles Dictionary ---
#ROLES = {
#    "default": "You are a helpful assistant.",
#    "developer": "You are a software developer.",
#    "teacher": "You are a knowledgeable teacher.",
#    "doctor": "You are a medical professional.",
#}


ROLES = {
    "General Assistant": {
        "system_prompt": "You are a helpful AI assistant. Be friendly, informative, and professional.",
        "icon": "🤖",
    },
    "Customer Service": {
        "system_prompt": """You are a professional customer service representative. You should:
        - Be polite, empathetic, and patient
        - Focus on solving customer problems
        - Ask clarifying questions when needed
        - Offer alternatives and solutions
        - Maintain a helpful and positive tone
        - If you can't solve something, explain how to escalate""",
        "icon": "📞",
    },
    "Technical Support": {
        "system_prompt": """You are a technical support specialist. You should:
        - Provide clear, step-by-step technical solutions
        - Ask about system specifications and error messages
        - Suggest troubleshooting steps in logical order
        - Explain technical concepts in simple terms
        - Be patient with non-technical users""",
        "icon": "⚙️",
    },
    "Teacher/Tutor": {
        "system_prompt": """You are an educational tutor. You should:
        - Explain concepts clearly and simply
        - Use examples and analogies to aid understanding
        - Encourage learning and curiosity
        - Break down complex topics into manageable parts
        - Provide practice questions or exercises when appropriate""",
        "icon": "📚",
    },
}  

# Fungsi extract text dari PDF
def extract_text_from_pdf(pdf_file):
    import PyPDF2
    text = ""
    reader = PyPDF2.PdfReader(pdf_file)  # langsung pakai PdfReader
    for page in reader.pages:
        text += page.extract_text() or ""  # tambahkan "" kalau None
    return text

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    st.write("You can configure the chatbot settings here.")
    # --- Sidebar Role Selection ---
    st.subheader("🎭 Select Role")
    selected_role = st.selectbox(
        "Choose assistant role:", options=list(ROLES.keys()), index=0
    )

    # --- Sidebar Knowledge Base ---
    st.subheader("📚 Knowledge Base")
    uploaded_files = st.file_uploader(
        "Upload a PDF file", type=["pdf"],
        accept_multiple_files=True
        )
    
    #Processing uploaded files
    if uploaded_files:
        # Inisialisasi 'knowledge_base' di session_state jika belum ada
        if "knowledge_base" not in st.session_state:
            st.session_state.knowledge_base = ""

        # Ekstrak teks dari file-file yang baru diunggah
        new_knowledge = ""
        for pdf_file in uploaded_files:
            st.write(f"📄 Processing: {pdf_file.name}")
            pdf_text = extract_text_from_pdf(pdf_file)
            if pdf_text:
                # Tambahkan teks dari PDF ke variabel dengan format penanda
                new_knowledge += f"\n\n=== DOCUMENT: {pdf_file.name} ===\n{pdf_text}"

        # Perbarui basis pengetahuan jika ada konten baru dan belum ada sebelumnya
        if new_knowledge and new_knowledge not in st.session_state.knowledge_base:
            st.session_state.knowledge_base += new_knowledge
            st.success(f"✅ Processed {len(uploaded_files)} document(s)")
    
    # Tombol untuk menghapus seluruh basis pengetahuan
    if st.button("🗑️ Clear Knowledge Base"):
        st.session_state.knowledge_base = ""
        st.success("Knowledge base cleared!")

    # Tampilkan status basis pengetahuan (jumlah kata)
    if "knowledge_base" in st.session_state and st.session_state.knowledge_base:
        word_count = len(st.session_state.knowledge_base.split())
        st.metric("Knowledge Base", f"{word_count} words")

# --- Session State Initialization ---
# Inisialisasi riwayat pesan jika belum ada
if "messages" not in st.session_state:
    st.session_state.messages = []

# Inisialisasi peran saat ini jika belum ada
if "current_role" not in st.session_state:
    st.session_state.current_role = selected_role

# Atur ulang percakapan jika pengguna mengganti peran AI
if st.session_state.current_role != selected_role:
    st.session_state.messages = []  # Kosongkan riwayat chat
    st.session_state.current_role = selected_role
    st.rerun()  # Muat ulang aplikasi untuk menerapkan perubahan


#--- Main Chat Interface ---
# Display the selected role and its icon
st.markdown(f"### Selected Role: {selected_role} {ROLES[selected_role]['icon']}")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"]) 

# Input chat dari pengguna
if prompt := st.chat_input("Type your message here..."):
    st.session_state.messages.append({"role": "user", "content": prompt})  
    with st.chat_message("user"):
        st.markdown(prompt)

    #system_prompt =ROLES[selected_role]
    #response = model.generate_content(prompt)

    with st.chat_message("assistant"):
        # Initialize Generative AI model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Develop prompt with system role
        system_prompt = ROLES[selected_role]["system_prompt"]

        # Tambahkan konteks dari basis pengetahuan jika tersedia
        if "knowledge_base" in st.session_state and st.session_state.knowledge_base:
            system_prompt += f"""

            IMPORTANT: You have access to the following knowledge base from uploaded documents. Use this information to answer questions when relevant:

            {st.session_state.knowledge_base}

            When answering questions, prioritize information from the knowledge base when applicable. If the answer is found in the uploaded documents, mention which document it came from.
            """

        # Konversi riwayat pesan ke format yang sesuai untuk Gemini
        chat_history = []

        # Tambahkan prompt sistem sebagai pesan pertama jika ini awal percakapan
        if not st.session_state.messages[:-1]:
            chat_history.append({"role": "user", "parts": [system_prompt]})
            chat_history.append(
                {
                    "role": "model",
                    "parts": [
                        "I understand. I'll act according to my role and use the knowledge base when relevant. How can I help you?"
                    ],
                }
            )

        # Tambahkan riwayat percakapan sebelumnya (semua kecuali pesan terakhir dari pengguna)
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            chat_history.append({"role": role, "parts": [msg["content"]]})

        # Start a chat session if you want streaming responses
        chat = model.start_chat(history=chat_history)
        
        # Gabungkan prompt sistem dengan pertanyaan pengguna hanya untuk interaksi pertama
        if not st.session_state.messages[:-1]:
            full_prompt = f"{system_prompt}\n\nUser question: {prompt}"
        else:
            full_prompt = prompt

        # Kirim pesan dan dapatkan respons secara streaming
        response = chat.send_message(full_prompt, stream=True)

        # Tampilkan respons secara streaming (efek ketikan)
        response_text = ""
        response_container = st.empty()
        for chunk in response:
            if chunk.text:
                response_text += chunk.text
                # Tambahkan kursor berkedip untuk efek visual
                response_container.markdown(response_text + "▌")

        # Tampilkan respons final tanpa kursor
        response_container.markdown(response_text)

    # Tambahkan respons dari asisten ke riwayat chat untuk ditampilkan di interaksi selanjutnya
    st.session_state.messages.append({"role": "assistant", "content": response_text})
