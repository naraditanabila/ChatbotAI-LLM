from logging import PlaceHolder
from openai import OpenAI
import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from crawlbase import CrawlingAPI
import re

# Load environment variables from .env file
load_dotenv()

# Get the API key from environment variables
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
crawling_api = CrawlingAPI({"token": os.getenv("CRAWLING_API_KEY")})

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

st.set_page_config(page_title="AI Chatbot App", page_icon="🤖", layout="wide")
st.title("My First AI Chatbot App")
st.write("This is a simple chatbot app using Google Gemini AI.")

# Initialize the Generative AI model
model = genai.GenerativeModel('gemini-1.5-flash')

MENU = {
        "Price Researcher": {
            "system_prompt": "Kamu adalah seorang peneliti harga. Tugas kamu adalah menemukan harga terbaik untuk produk di berbagai platform e-commerce.",
            "icon": "💰",
        },
        "Offering Reviewer": {
            "system_prompt": "Kamu adalah seorang reviewer penawaran harga dari vendor. Tugas kamu adalah meninjau dan menganalisis penawaran bisnis dari vendor, memastikan penawaran tersebut memenuhi persyaratan pelanggan dan kompetitif di pasar berdasarkan platform e-commerce.",
            "icon": "📄",
        },
        "Product Scraper": {
            "system_prompt": "Kamu adalah ilmuwan produk. Tugas kamu adalah memberikan informasi produk dari platform e-commerce seperti Tokopedia dan Shopee, termasuk detail produk, harga, dan ulasan.",
            "icon": "🔍",
        },
        "Knowledge Base Manager": {
            "system_prompt": "Kamu adalah knowledge base manager. Tugas kamu adalah mengelola dan memelihara basis pengetahuan untuk chatbot, termasuk mengunggah dan memproses dokumen.",
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

# Fungsi extract text dari file Excel
def extract_text_from_excel(excel_file):
    import pandas as pd
    text = ""
    df = pd.read_excel(excel_file)
    for column in df.columns:
        text += f"{column}:\n"
        text += "\n".join(df[column].astype(str).tolist()) + "\n\n"
    return text
    
# Fungsi cari url produk di Tokopedia dengan nama produk dan review lebih dari 1, pilih yang memiliki harga tertinggi
def find_tokopedia_product_url(product_name, min_reviews=1):
    search_url = f"https://www.tokopedia.com/search?st=product&q={product_name}"
    options = {
        'ajax_wait': 'true',
        'page_wait': '5000'
    }
    response = crawling_api.get(search_url, options)

    if response.get('headers', {}).get('pc_status') == '200':
        html_content = response.get('body', b'').decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find product links with more than min_reviews reviews
        products = soup.select('a[data-testid="lnkProductName"]')
        highest_price_product = None
        highest_price = 0

        for product in products:
            reviews_count = int(product.select_one('span[data-testid="lblProductReviewCount"]').text.strip())
            if reviews_count >= min_reviews:
                price_text = product.select_one('span[data-testid="lblProductPrice"]').text.strip()
                price_value = int(price_text.replace('Rp', '').replace('.', '').strip())
                if price_value > highest_price:
                    highest_price = price_value
                    highest_price_product = product['href']
        
        return highest_price_product
    
    print("No product found with the specified criteria.")
    return None

# Fungsi cari url produk di Shopee dengan nama produk dan review lebih dari 1, pilih yang memiliki harga tertinggi
def find_shopee_product_url(product_name, min_reviews=1):
    search_url = f"https://shopee.co.id/search?keyword={product_name}"
    options = {
        'ajax_wait': 'true',
        'page_wait': '5000'
    }
    response = crawling_api.get(search_url, options)

    if response.get('headers', {}).get('pc_status') == '200':
        html_content = response.get('body', b'').decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find product links with more than min_reviews reviews
        products = soup.select('div[data-sqe="item"]')
        highest_price_product = None
        highest_price = 0

        for product in products:
            reviews_count_text = product.select_one('div[data-sqe="rating"]').text.strip()
            reviews_count = int(reviews_count_text.split()[0].replace('.', '').replace(',', '')) if reviews_count_text else 0
            
            if reviews_count >= min_reviews:
                price_text = product.select_one('span[data-sqe="price"]').text.strip()
                price_value = int(price_text.replace('Rp', '').replace('.', '').strip())
                if price_value > highest_price:
                    highest_price = price_value
                    highest_price_product = product.select_one('a')['href']
        
        return highest_price_product
    
    print("No product found with the specified criteria.")
    return None

# Fungsi crawlbase untuk mendapatkan informasi harga pada halaman produk Tokopedia
def scrape_tokopedia_product_page(url):
    options = {
        'ajax_wait': 'true',
        'page_wait': '5000'
    }
    response = crawling_api.get(url, options)

    if response.get('headers', {}).get('pc_status') == '200':
        html_content = response.get('body', b'').decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract product details
        product_name = soup.select_one('h1[data-testid="lblPDPDetailProductName"]').text.strip()
        price_text = soup.select_one('div[data-testid="lblPDPDetailProductPrice"]').text.strip()
        price_value = int(price_text.replace('Rp', '').replace('.', '').strip())
        elem = soup.select_one('p.css-19y0pwk-unf-heading.e1qvo2ff8')
        if elem:
            text = elem.text.strip()
        # contoh: "15 rating • 6 ulasan"
            match = re.findall(r'\d+', text)
            rating_count = int(match[0])

        return {
            "name": product_name,
            "price": price_value,
            "rating_count": rating_count,
            "url": url
        }
    
    print("Failed to scrape the product page.")
    return None

# Fungsi crawlbase untuk mendapatkan informasi harga pada halaman produk Shopee
def scrape_shopee_product_page(url):
    options = {
        'ajax_wait': 'true',
        'page_wait': '5000'
    }
    response = crawling_api.get(url, options)

    if response.get('headers', {}).get('pc_status') == '200':
        html_content = response.get('body', b'').decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract product details
        product_name = soup.select_one('div[data-sqe="name"]').text.strip()
        price_text = soup.select_one('div[data-sqe="price"]').text.strip()
        price_value = int(price_text.replace('Rp', '').replace('.', '').strip())
        reviews_count_text = soup.select_one('div[data-sqe="rating"]').text.strip()
        reviews_count = int(reviews_count_text.split()[0].replace('.', '').replace(',', '')) if reviews_count_text else 0

        return {
            "name": product_name,
            "price": price_value,
            "reviews_count": reviews_count,
            "url": url
        }
    
    print("Failed to scrape the product page.")
    return None

# Fungsi update knowledge base dari hasil scraping
def update_knowledge_base(product_data, platform):
    """
    Update the knowledge base with product data from scraping.
    
    Args:
        product_data (dict): Dictionary containing product details.
        platform (str): The e-commerce platform (e.g., "Tokopedia", "Shopee").
    
    Returns:
        str: Updated knowledge base entry.
    """
    if not product_data:
        return ""

    entry = f"\n\n=== {platform.upper()} PRODUCT ===\n"
    entry += f"Name: {product_data['name']}\n"
    entry += f"Price: Rp{product_data['price']:,}\n"
    entry += f"URL: {product_data['url']}\n"

    return entry
    
# Fungsi cek kewajaran harga produk
def is_price_reasonable(product_price, highest_price, margin=0.2):
    """
    Cek apakah harga produk wajar tidak melebihi harga tertinggi pasaran yang valid dikalikan margin.
    
    Args:
        product_price (float): Harga produk yang akan dicek.
        highest_price (float): Harga tertinggi dari e-commerce.
        margin (float): Margin yang diizinkan, default 20% (0.2).
    
    Returns:
        bool: True jika harga produk wajar, False jika tidak.
    """
    return product_price <= highest_price * (1 + margin)
    

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    st.write("You can configure the chatbot settings here.")

    # --- Sidebar Input Nama Proyek dengan contoh nama proyek yang otomatis replace ketika mulai input---
    st.subheader("📝 Project Name")
    selected_project = st.text_input(
        "Enter the name of your project",
        value="My Project",
        placeholder="e.g., My Project, AI Chatbot, Price Researcher"
    )

    # --- Sidebar Menu Selection ---
    st.subheader("📋 Select Menu")
    selected_menu = st.selectbox(
        "Choose a menu option:",
        options=list(MENU.keys()),
        index=0
    )

    # --- Sidebar E-commerce Selection ---
    st.subheader("🛒 E-commerce Selection")
    st.write("You can select multiple platforms to compare prices.")
    selected_ecommerce = st.multiselect(
        "Select E-commerce Platform",
        ["Tokopedia", "Shopee", "Summary Solution"],
        default=["Tokopedia"]
    )

    # --- Sidebar Input Margin ---
    st.subheader("💰 Price Margin")
    margin = st.slider(
        "Set the acceptable price margin for products",
        min_value=0.0,
        max_value=0.5,
        value=0.2,  # Default to 20%
        step=0.01
    )

    # --- Sidebar Download Knowledge Base ---
    st.subheader("📥 Download Knowledge Base")
    if st.button("Download Knowledge Base"):
        if "knowledge_base" in st.session_state and st.session_state.knowledge_base:
            # Simpan basis pengetahuan ke file excel
            import pandas as pd
            knowledge_base = st.session_state.knowledge_base.split("\n\n")
            df = pd.DataFrame(knowledge_base, columns=["Knowledge Base"])
            file_name = f"knowledge_base_{selected_project}.xlsx"
            df.to_excel(file_name, index=False)
            st.success(f"Knowledge base saved to {file_name}")
        else:
            st.warning("No knowledge base available to download.")
    
    # File uploader untuk mengunggah file Excel
    uploaded_files = st.file_uploader(
        "Upload Excel files to build the knowledge base",
        type=["xlsx", "xls"],
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
    

# --- Session State Initialization ---
# Inisialisasi riwayat pesan jika belum ada
if "messages" not in st.session_state:
    st.session_state.messages = []

# Inisialisasi peran saat ini jika belum ada
if "current_project" not in st.session_state:
    st.session_state.current_project = selected_project

# Atur ulang percakapan jika project berganti
if st.session_state.current_project != selected_project:
    st.session_state.messages = []  # Kosongkan riwayat chat
    st.session_state.current_project = selected_project  # Perbarui proyek saat ini
    st.rerun()  # Muat ulang aplikasi untuk menerapkan perubahan


#--- Main Chat Interface ---
# Display project's name
st.markdown(f"### Project Name: {selected_project}")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"]) 

# Input chat dari pengguna
if prompt := st.chat_input("Masukkan pertanyaan atau perintah Anda di sini..."):
    st.session_state.messages.append({"role": "user", "content": prompt})  
    with st.chat_message("user"):
        st.markdown(prompt)

    #system_prompt =ROLES[selected_role]
    #response = model.generate_content(prompt)

    with st.chat_message("assistant"):
        # Initialize Generative AI model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Develop prompt with system menu selection
        system_prompt = MENU[selected_menu]["system_prompt"]

        # Tambahkan konteks dari basis pengetahuan jika tersedia
        if "knowledge_base" in st.session_state and st.session_state.knowledge_base:
            system_prompt += f"""

            PENTING: Anda memiliki akses ke basis pengetahuan berikut dari dokumen yang diunggah. Gunakan informasi ini untuk menjawab pertanyaan jika relevan:

            {st.session_state.knowledge_base}

            Saat menjawab pertanyaan, prioritaskan informasi dari knowledge base jika relevan. Jika jawabannya ditemukan dalam dokumen yang diunggah, sebutkan dari dokumen mana jawabannya berasal.
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
                        "Saya mengerti. Saya akan bertindak sesuai peran saya dan menggunakan basis pengetahuan ini jika relevan. Bagaimana saya bisa membantu Anda?"
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
            full_prompt = f"{system_prompt}\n\nPertanyaan User: {prompt}"
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

# Scraping product page and saving data
url = 'https://www.tokopedia.com/ruijie/ruijie-rg-rap2260-g-reyee-wi-fi-6-ax1800-ceiling-access-point-1731377086149854387'
product_data = scrape_tokopedia_product_page(url)
print(product_data)
