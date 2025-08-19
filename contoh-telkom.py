# Impor pustaka (library) yang diperlukan
from openai import OpenAI
import streamlit as st
import os
from dotenv import load_dotenv
import PyPDF2
import tempfile

# Muat variabel lingkungan dari file .env (untuk menyimpan kunci API)
load_dotenv()

st.title("🤖 AI Assistant with Role-Play & Knowledge Base (Telkom AI)")


# Konfigurasi Telkom API menggunakan kunci yang diambil dari environment
@st.cache_resource
def get_telkom_client():
    api_key = os.getenv("TELKOM_API_KEY")
    if not api_key:
        st.error("TELKOM_API_KEY not found in environment variables!")
        return None

    return OpenAI(
        api_key=api_key,
        base_url="https://telkom-ai-dag-api.apilogy.id/Telkom-LLM/0.0.4/llm",
        default_headers={"x-api-key": api_key},
    )


# Daftar peran (role) yang telah ditentukan sebelumnya untuk AI
# Setiap peran memiliki prompt sistem (perintah) dan ikon sendiri
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


# Fungsi untuk mengekstrak teks dari file PDF yang diunggah
def extract_text_from_pdf(pdf_file):
    """Mengekstrak teks dari file PDF yang diunggah"""
    try:
        # Buat file sementara untuk menyimpan PDF yang diunggah
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_file.getvalue())
            tmp_file_path = tmp_file.name

        # Buka dan baca file PDF sementara
        with open(tmp_file_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            # Loop setiap halaman dalam PDF untuk mengambil teksnya
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"

        # Hapus file sementara setelah selesai diproses
        os.unlink(tmp_file_path)
        return text
    except Exception as e:
        # Tampilkan pesan error jika gagal mengekstrak teks
        st.error(f"Error extracting PDF text: {str(e)}")
        return None


# --- Bagian Sidebar untuk Konfigurasi ---
with st.sidebar:
    st.header("⚙️ Configuration")

    # Pilihan untuk mengubah peran (role) AI
    st.subheader("🎭 Select Role")
    selected_role = st.selectbox(
        "Choose assistant role:", options=list(ROLES.keys()), index=0
    )

    # Bagian untuk mengunggah file PDF sebagai basis pengetahuan (knowledge base)
    st.subheader("📚 Knowledge Base")
    uploaded_files = st.file_uploader(
        "Upload PDF documents:", type=["pdf"], accept_multiple_files=True
    )

    # Proses file yang diunggah
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

# --- Inisialisasi Session State ---
# Session state digunakan untuk menyimpan data antar interaksi pengguna

# Inisialisasi client Telkom jika belum ada
if "telkom_client" not in st.session_state:
    st.session_state["telkom_client"] = get_telkom_client()

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

# --- Antarmuka Chat Utama ---

# Tampilkan peran yang sedang aktif
st.markdown(f"**Current Role:** {ROLES[selected_role]['icon']} {selected_role}")

# Tampilkan riwayat percakapan dari sesi sebelumnya
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input chat dari pengguna
if prompt := st.chat_input("What can I help you with?"):
    # Tambahkan pesan pengguna ke riwayat chat
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Hasilkan respons dari asisten AI
    with st.chat_message("assistant"):
        # Periksa apakah client Telkom tersedia
        if not st.session_state["telkom_client"]:
            st.error("Telkom API client not available. Please check your API key.")
            st.stop()

        client = st.session_state["telkom_client"]

        # Bangun prompt sistem dengan instruksi peran
        system_prompt = ROLES[selected_role]["system_prompt"]

        # Tambahkan konteks dari basis pengetahuan jika tersedia
        if "knowledge_base" in st.session_state and st.session_state.knowledge_base:
            system_prompt += f"""

            IMPORTANT: You have access to the following knowledge base from uploaded documents. Use this information to answer questions when relevant:

            {st.session_state.knowledge_base}

            When answering questions, prioritize information from the knowledge base when applicable. If the answer is found in the uploaded documents, mention which document it came from.
            """

        # Bangun pesan untuk API Telkom
        messages = []

        # Tambahkan sistem prompt sebagai pesan pertama jika ini awal percakapan
        if not st.session_state.messages[:-1]:
            messages.append({"role": "system", "content": system_prompt})

        # Tambahkan riwayat percakapan sebelumnya (semua kecuali pesan terakhir dari pengguna)
        for msg in st.session_state.messages[:-1]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Tambahkan pesan pengguna saat ini
        messages.append({"role": "user", "content": prompt})

        try:
            # Kirim pesan ke API Telkom dan dapatkan respons
            response = client.chat.completions.create(
                model="telkom-ai", messages=messages, stream=True
            )

            # Tampilkan respons secara streaming (efek ketikan)
            response_text = ""
            response_container = st.empty()

            for chunk in response:
                if chunk.choices[0].delta.content:
                    response_text += chunk.choices[0].delta.content
                    # Tambahkan kursor berkedip untuk efek visual
                    response_container.markdown(response_text + "▌")

            # Tampilkan respons final tanpa kursor
            response_container.markdown(response_text)

        except Exception as e:
            st.error(f"Error calling Telkom API: {str(e)}")
            response_text = (
                "Sorry, I encountered an error while processing your request."
            )
            st.markdown(response_text)

    # Tambahkan respons dari asisten ke riwayat chat untuk ditampilkan di interaksi selanjutnya
    st.session_state.messages.append({"role": "assistant", "content": response_text})

# --- Petunjuk Penggunaan di Bagian Bawah ---
with st.expander("ℹ️ How to use"):
    st.markdown("""
    ### Role-Playing:
    - Select different roles from the sidebar
    - Each role has specific behavior and expertise
    - The conversation resets when you change roles

    ### Knowledge Base:
    - Upload PDF documents in the sidebar
    - Ask questions about the content in your documents
    - The AI will reference the uploaded documents when answering
    - You can upload multiple PDFs

    ### Telkom AI Integration:
    - This chatbot now uses Telkom AI instead of Google Gemini
    - Powered by Telkom University's AI model
    - Requires TELKOM_API_KEY in your .env file

    ### Tips:
    - Be specific in your questions for better answers
    - The AI will mention which document information came from
    - Clear the knowledge base to start fresh
    """)

# Display API status in sidebar
with st.sidebar:
    st.divider()
    if st.session_state.get("telkom_client"):
        st.success("✅ Telkom AI Connected")
    else:
        st.error("❌ Telkom AI Connection Failed")