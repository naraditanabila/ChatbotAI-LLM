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

st.set_page_config(page_title="Chatbot CPE for Solution Team", page_icon="🤖", layout="wide")
st.title("AI Chatbot App for Solution Team")
st.write("This is a simple chatbot app using Google Gemini AI.")

# Initialize the Generative AI model
model = genai.GenerativeModel('gemini-1.5-flash')

ROLE = {
        "Price Researcher": {
            "system_prompt": "Kamu adalah seorang peneliti harga. Tugas kamu adalah menemukan harga terbaik untuk produk di berbagai platform e-commerce. Jangan terlalu banyak bertanya tentang spesifikasi teknis. Kamu dapat menggunakan asumsi spek teknis sesuai rekomendasi kamu",
            "icon": "💰",
            "description": "Sebagai peneliti harga, chatbot ini akan mencari dan membandingkan harga produk dari berbagai sumber untuk memberikan rekomendasi terbaik."
        },
        "Offering Reviewer": {
            "system_prompt": "Kamu adalah seorang reviewer penawaran harga dari vendor. Tugas kamu adalah meninjau dan menganalisis penawaran bisnis dari vendor, memastikan penawaran tersebut memenuhi persyaratan pelanggan dan kompetitif di pasar berdasarkan platform e-commerce.",
            "icon": "📄",
            "description": "Sebagai reviewer penawaran, chatbot ini akan mengevaluasi dan memberikan masukan tentang penawaran harga yang diajukan oleh vendor."
        },
        "Knowledge Base Manager": {
            "system_prompt": "Kamu adalah knowledge base manager. Tugas kamu adalah mengelola dan memelihara basis pengetahuan untuk chatbot, termasuk mengunggah dan memproses dokumen.",
            "icon": "📚",
            "description": "Sebagai knowledge base manager, chatbot ini akan bertanggung jawab untuk memastikan bahwa informasi dalam basis pengetahuan selalu diperbarui dan relevan."
        },
    }

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

#Fungsi mendapatkan harga produk tertinggi dari beberapa e-commerce
def get_max_product_price(product_name, margin=0.2):
    """
    Get the maximum vendor price for a product across multiple e-commerce platforms.
    
    Args:
        product_name (str): The name of the product to search for.
        margin (float): The acceptable price margin for products.
    
    Returns:
        dict: A dictionary containing the platform and the maximum price found.
    """
    # Cari produk di Tokopedia
    tokopedia_url = find_tokopedia_product_url(product_name)
    if tokopedia_url:
        tokopedia_data = scrape_tokopedia_product_page(tokopedia_url)
        if tokopedia_data:
            tokopedia_data['platform'] = 'Tokopedia'
            tokopedia_data['price'] *= (1 + margin)  # Apply margin
        else:
            tokopedia_data = None
    else:
        tokopedia_data = None

    # Cari produk di Shopee
    shopee_url = find_shopee_product_url(product_name)
    if shopee_url:
        shopee_data = scrape_shopee_product_page(shopee_url)
        if shopee_data:
            shopee_data['platform'] = 'Shopee'
            shopee_data['price'] *= (1 + margin)  # Apply margin
        else:
            shopee_data = None
    else:
        shopee_data = None

    # Bandingkan harga dan pilih yang tertinggi
    max_price_data = None
    if tokopedia_data and shopee_data:
        max_price_data = tokopedia_data if tokopedia_data['price'] > shopee_data['price'] else shopee_data
    elif tokopedia_data:
        max_price_data = tokopedia_data
    elif shopee_data:
        max_price_data = shopee_data

    return max_price_data

# Fungsi untuk format hasil analisis harga vendor
def format_vendor_price_analysis(analysis):
    """
    Format the vendor price analysis for display.
    
    Args:
        analysis (dict): The analysis result containing platform and price.
    
    Returns:
        str: Formatted string for display.
    """
    if not analysis:
        return "No vendor prices found."
    
    platform = analysis['platform']
    price = analysis['price']
    
    entry = f"### Vendor Price Analysis\n"
    entry += f"Platform: {platform}\n"
    entry += f"Price: Rp{price:,}\n"
    entry += f"URL: {analysis['url']}\n"
    entry += f"Product Name: {analysis['name']}\n"
    entry += f"Reviews Count: {analysis.get('reviews_count', 'N/A')}\n"
    if platform == "Tokopedia":
        entry += f"Rating Count: {analysis.get('rating_count', 'N/A')}\n"
    elif platform == "Shopee":
        entry += f"Reviews Count: {analysis.get('reviews_count', 'N/A')}\n"
    else:
        entry += "Platform not recognized.\n"    
    

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

    # --- Sidebar Role Selection ---
    st.subheader("👤 Role Selection")
    selected_role = st.selectbox(
        "Select your role",
        list(ROLE.keys()),
        format_func=lambda x: f"{ROLE[x]['icon']} {x}"
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

    # --- Sidebar Knowledge Base ---
    st.subheader("📥 Knowledge Base")
    # Inisialisasi 'knowledge_base' di session_state jika belum ada
    if "knowledge_base" not in st.session_state:
        st.session_state.knowledge_base = ""
    # Tombol untuk menambah basis pengetahuan dari chat terakhir
    if st.button("Add Knowledge from Chat"):
        # Panggil file knowledge_base.xlsx untuk memuat knowledge base
        if "knowledge_base_file" not in st.session_state:
            st.session_state.knowledge_base_file = "knowledge_base.xlsx"

        # Muat basis pengetahuan dari file jika ada
        if "knowledge_base" not in st.session_state:
            try:
                with open(st.session_state.knowledge_base_file, "r") as f:
                    st.session_state.knowledge_base = f.read()
            except FileNotFoundError:
                st.session_state.knowledge_base = ""
        
        # Ambil pesan terakhir dari chat
        if st.session_state.messages:
            last_message = st.session_state.messages[-1]["content"]
            # Tambahkan pesan terakhir ke basis pengetahuan
            st.session_state.knowledge_base += f"\n\n=== CHAT ENTRY ===\n{last_message}"
            st.success("Knowledge base updated with the latest chat entry.")
        else:
            st.warning("No chat messages available to add to the knowledge base.")
    
    # Tombol untuk mengunduh basis pengetahuan sebagai file Excel
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
        for excel_file in uploaded_files:
            st.write(f"📄 Processing: {excel_file.name}")
            excel_text = extract_text_from_excel(excel_file)
            if excel_text:
                # Tambahkan teks dari Excel ke variabel dengan format penanda
                new_knowledge += f"\n\n=== DOCUMENT: {excel_file.name} ===\n{excel_text}"

        # Perbarui basis pengetahuan jika ada konten baru dan belum ada sebelumnya
        if new_knowledge and new_knowledge not in st.session_state.knowledge_base:
            st.session_state.knowledge_base += new_knowledge
            st.success(f"✅ Processed {len(uploaded_files)} document(s)")
    

# --- Session State Initialization ---

# Inisialisasi model Gemini jika belum ada
if "gemini_model" not in st.session_state:
    st.session_state["gemini_model"] = "gemini-2.5-flash"

# Inisialisasi role jika belum ada
if "current_role" not in st.session_state:
    st.session_state.current_role = selected_role

# Inisialisasi pesan dari assistant sesuai role yang dipilih
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Tambahkan pesan selamat datang sesuai role
    if selected_role in ROLE:
        welcome_message = f"**{selected_role} {ROLE[selected_role]['icon']}**: {ROLE[selected_role]['description']}"
        st.session_state.messages.append({"role": "assistant", "content": welcome_message})

# Inisialisasi proyek saat ini jika belum ada
if "current_project" not in st.session_state:
    st.session_state.current_project = selected_project

if (st.session_state.current_role != selected_role):
    # Tambahkan pesan selamat datang untuk role baru
    st.session_state.current_role = selected_role  # Perbarui role saat ini
    welcome_message = f"**{selected_role} {ROLE[selected_role]['icon']}**: {ROLE[selected_role]['description']}"
    st.session_state.messages.append({"role": "assistant", "content": welcome_message})

# Atur ulang percakapan jika role atau project berganti
if (st.session_state.current_project != selected_project):
    st.session_state.messages = []  # Kosongkan riwayat chat
    st.session_state.current_project = selected_project  # Perbarui proyek saat ini
    st.rerun()  # Muat ulang aplikasi untuk menerapkan perubahan
    

#--- Main Chat Interface ---
# Display project's name
st.markdown(f"### Project Name: {selected_project}")

# Tampilkan riwayat chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# Input chat dari pengguna
if prompt := st.chat_input("What can I help you with?"):
    # Tampilkan pesan pengguna di chat
    with st.chat_message("user"):
        st.markdown(prompt)

    # Hasilkan respons dari asisten AI
    with st.chat_message("assistant"):
        # Inisialisasi model Generative AI
        model = genai.GenerativeModel(st.session_state["gemini_model"])

        # Bangun prompt sistem dengan instruksi peran dan konteks sebelumnya
        system_prompt = ROLE[selected_role]["system_prompt"]
        
        # Tambahkan konteks bahwa ini adalah kelanjutan percakapan jika ada riwayat
        if len(st.session_state.messages) > 1:  # Jika ada lebih dari pesan selamat datang
            system_prompt += "\n\nThis is a continuation of our conversation. Please maintain context from previous messages."

        # Identifikasi nama produk yang akan dianalisis
        if selected_role == "Price Researcher":
            # Extract product name from query
            product_name = prompt
            # Tambahkan nama produk ke dalam prompt sistem
            system_prompt += f"\n\n=== PRODUCT NAME ===\n{product_name}"

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
        if not st.session_state.messages:
            chat_history.append({"role": "user", "parts": [system_prompt]})
            chat_history.append(
                {
                    "role": "model",
                    "parts": [
                        "I understand. I'll act according to my role and use the knowledge base when relevant. How can I help you?"
                    ],
                }
            )
        # Tambahkan riwayat percakapan sebelumnya
        for msg in st.session_state.messages:
            role = "user" if msg["role"] == "user" else "model"
            chat_history.append({"role": role, "parts": [msg["content"]]})
        # Tambahkan pesan user terbaru ke chat_history
        chat_history.append({"role": "user", "parts": [prompt]})

        # Mulai sesi chat dengan riwayat yang sudah ada
        chat = model.start_chat(history=chat_history)

        # Kirim pesan dan dapatkan respons secara streaming
        response = chat.send_message(prompt, stream=True)

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

    # Setelah proses AI selesai, baru tambahkan pesan user dan asisten ke session_state
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.messages.append({"role": "assistant", "content": response_text})

# Scraping product page and saving data
#url = 'https://shopee.co.id/Ruijie-Reyee-RG-RAP2200(F)-Wireless-Ceiling-Access-Point-WiFi-5-1200M-Dual-Band-PoE-Garansi-Resmi-i.517307496.42257544573'
#product_data = scrape_shopee_product_page(url)
#print(product_data)
