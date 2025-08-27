from logging import PlaceHolder
from openai import OpenAI
import streamlit as st
import os
import io
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from crawlbase import CrawlingAPI
import base64
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from price_researcher import extract_product_name, extract_price

# Define roles and their configurations
ROLE = {
    "Price Researcher": {
        "icon": "💰",
        "description": "Sebagai peneliti harga, saya akan mencari dan membandingkan harga produk dari berbagai sumber untuk memberikan rekomendasi harga terbaik."
    },
    "Offering Reviewer": {
        "icon": "📋",
        "description": "Sebagai peninjau penawaran, saya akan membantu Anda meninjau dan mengevaluasi penawaran bisnis."
    }
}

# Initialize session state variables
if "gemini_model" not in st.session_state:
    st.session_state["gemini_model"] = "gemini-2.5-flash"

if "current_role" not in st.session_state:
    # Set default role
    default_role = "Price Researcher"
    st.session_state.current_role = default_role
    
    # Initialize messages with welcome message for default role
    st.session_state.messages = []
    welcome_message = f"**{st.session_state.current_role} {ROLE[st.session_state.current_role]['icon']}**: {ROLE[st.session_state.current_role]['description']}"
    st.session_state.messages = [{"role": "assistant", "content": welcome_message}]
elif "messages" not in st.session_state:
    st.session_state.messages = []
    # Add welcome message for current role if messages list is empty
    welcome_message = f"**{st.session_state.current_role} {ROLE[st.session_state.current_role]['icon']}**: {ROLE[st.session_state.current_role]['description']}"
    st.session_state.messages = [{"role": "assistant", "content": welcome_message}]

if "current_project" not in st.session_state:
    st.session_state.current_project = "My Project"  # Default project name

#if "knowledge_base" not in st.session_state:
#    st.session_state.knowledge_base = {"products": []}

# Knowledge Base Management Functions
def load_knowledge_base():
    """Load knowledge base from Excel file"""
    try:
        df = pd.read_excel("knowledge_base.xlsx")
        products = []
        for _, row in df.iterrows():
            products.append({
                'product_name': row['product_name'],
                'nett_price': float(row['nett_price']),
                'platform': row['platform'],
                'url': row['link']
            })
        return {'products': products}
    except FileNotFoundError:
        return {'products': []}

def save_to_knowledge_base(product_data):
    """Save new product data to knowledge base"""
    try:
        # Load existing data
        try:
            df = pd.read_excel("knowledge_base.xlsx")
        except FileNotFoundError:
            df = pd.DataFrame(columns=['product_name', 'nett_price', 'platform', 'link'])
        
        # Add new data
        new_row = pd.DataFrame([{
            'product_name': product_data['name'],
            'nett_price': product_data['price'],
            'platform': product_data['platform'],
            'link': product_data['url']
        }])
        
        df = pd.concat([df, new_row], ignore_index=True)
        
        # Save back to Excel
        df.to_excel("knowledge_base.xlsx", index=False)
        return True
    except Exception as e:
        st.error(f"Error saving to knowledge base: {str(e)}")
        return False

def format_knowledge_base(knowledge_base):
    """Format knowledge base data for display"""
    text = "=== KNOWLEDGE BASE PRODUCTS ===\n\n"
    for product in knowledge_base['products']:
        text += f"Product: {product['product_name']}\n"
        text += f"Price: Rp {product['nett_price']:,.2f}\n"
        text += f"Platform: {product['platform']}\n"
        text += f"URL: {product['url']}\n"
        text += "---\n\n"
    return text

def download_knowledge_base():
    """Generate downloadable Excel file from knowledge base"""
    try:
        df = pd.read_excel("knowledge_base.xlsx")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"Error preparing download: {str(e)}")
        return None

def get_product_by_name(knowledge_base, product_name):
    """Search for a product in knowledge base by name"""
    for product in knowledge_base['products']:
        if product['product_name'].lower() == product_name.lower():
            return product
    return None

# Helper function untuk filter produk dari knowledge base
def filter_knowledge_base_products(platform=None, product_name=None):
    """
    Filter products from knowledge base based on platform and/or product name
    
    Args:
        platform (str, optional): Platform to filter by
        product_name (str, optional): Product name to search for
        
    Returns:
        list: List of matching products
    """
    if not st.session_state.get('knowledge_base') or not st.session_state.knowledge_base.get('products'):
        return []
        
    products = st.session_state.knowledge_base['products']
    
    if platform:
        products = [p for p in products if p['platform'] == platform]
    
    if product_name:
        products = [p for p in products if product_name.lower() in p['product_name'].lower()]
    
    return products

def extract_evaluation_from_response(response_text):
    """Extract evaluation details from assistant's response"""
    try:
        products = []
        lines = response_text.split('\n')
        current_product = {}
        
        for line in lines:
            line = line.strip()
            if "Product:" in line or "Produk:" in line:
                if current_product:
                    products.append(current_product)
                current_product = {}
                current_product['product_name'] = line.split(":", 1)[1].strip()
            elif "Quantity:" in line or "Jumlah:" in line:
                current_product['quantity'] = int(line.split(":", 1)[1].strip())
            elif "Unit Price:" in line or "Harga Satuan:" in line:
                price_str = line.split(":", 1)[1].strip()
                price_str = price_str.replace("Rp", "").replace(".", "").replace(",", "").strip()
                current_product['unit_price'] = float(price_str)
            elif "Reference URL:" in line or "URL:" in line:
                current_product['reference_url'] = line.split(":", 1)[1].strip()
        
        if current_product:
            products.append(current_product)
        
        return products
    except Exception as e:
        st.error(f"Error extracting evaluation data: {str(e)}")
        return None
    
def create_offering_template():
    """Create Excel file with offering template"""
    try:
        df = pd.DataFrame(columns=[
            'Product Name',
            'Quantity',
            'Unit Price',
            'Total Price'
        ])
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Offering Template')
        return buffer.getvalue()
    except Exception as e:
        st.error(f"Error creating offering template: {str(e)}")
        return None

def create_evaluation_excel(products, margin):
    """Create Excel file with evaluation results"""
    try:
        df_data = []
        
        for product in products:
            # Get maximum price from knowledge base
            kb_product = None
            if "knowledge_base" in st.session_state:
                for kb_item in st.session_state.knowledge_base['products']:
                    if product['product_name'].lower() in kb_item['product_name'].lower():
                        kb_product = kb_item
                        break
            
            if kb_product:
                # Calculate maximum allowed price
                max_price = float(kb_product['nett_price']) * product['quantity'] * (1 + margin)
                reference_url = kb_product['url']
                
                # Determine status
                status = "Wajar" if product['total_price'] <= max_price else "Tidak Wajar"
                
                df_data.append({
                    'Nama Produk': product['product_name'],
                    'Jumlah': product['quantity'],
                    'Harga Satuan': product['unit_price'],
                    'Total Harga Penawaran': product['total_price'],
                    'Harga Maksimum': max_price,
                    'Status': status,
                    'URL Referensi': reference_url
                })
        
        # Create DataFrame
        df = pd.DataFrame(df_data)
        
        # Format currency columns
        currency_columns = ['Harga Satuan', 'Total Harga Penawaran', 'Harga Maksimum']
        for col in currency_columns:
            df[col] = df[col].apply(lambda x: f"Rp {x:,.2f}")
        
        # Create Excel file in memory
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Hasil Evaluasi')
            
            # Auto-adjust columns width
            worksheet = writer.sheets['Hasil Evaluasi']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                )
                worksheet.column_dimensions[chr(65 + idx)].width = max_length + 2
        
        return buffer.getvalue()
    except Exception as e:
        st.error(f"Error creating Excel file: {str(e)}")
        return None

# Fungsi untuk mengunduh file Excel penawaran bisnis
def download_business_offering(data):
    """Generate downloadable Excel file from business offering data"""
    try:
        # Create DataFrame with specified columns
        df = pd.DataFrame(data, columns=[
            'Nama Produk',
            'Jumlah',
            'Harga Satuan',
            'Total Harga Penawaran',
            'Harga Maksimum',
            'Status',
            'URL Referensi'
        ])
        
        # Format currency columns
        currency_columns = ['Harga Satuan', 'Total Harga Penawaran', 'Harga Maksimum']
        for col in currency_columns:
            df[col] = df[col].apply(lambda x: f"Rp {float(x):,.2f}")
        
        # Create Excel file in memory
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Hasil Evaluasi')
            
            # Auto-adjust columns width
            worksheet = writer.sheets['Hasil Evaluasi']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                )
                worksheet.column_dimensions[chr(65 + idx)].width = max_length + 2
        
        return buffer.getvalue()
    except Exception as e:
        st.error(f"Error preparing business offering download: {str(e)}")
        return None
    
# Fungsi extract text dari file Excel
def extract_text_from_excel(excel_file):
    import pandas as pd
    text = ""
    df = pd.read_excel(excel_file)
    for column in df.columns:
        text += f"{column}:\n"
        text += "\n".join(df[column].astype(str).tolist()) + "\n\n"
    return text
    
# Fungsi cari url produk di Tokopedia dengan nama produk dan review lebih dari 1, pilih yang memiliki harga tertinggi dengan output berupa url dari produk tersebut
def scrape_tokopedia_search(query):
    url = f"https://www.tokopedia.com/search?q={query.replace(' ', '+')}"

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")  # jalan tanpa buka browser
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    driver.get(url)

    products = []
    items = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='divSRPContentProducts'] article")

    for item in items:
        try:
            name = item.find_element(By.CSS_SELECTOR, "div.prd_link-product-name").text
            price_text = item.find_element(By.CSS_SELECTOR, "div.prd_link-product-price").text
            sold_text = item.find_element(By.CSS_SELECTOR, "span.prd_label-integrity").text
            link = item.find_element(By.CSS_SELECTOR, "a").get_attribute("href")

            # convert harga ke int
            price = int(re.sub(r"[^\d]", "", price_text))

            # cari angka sold
            sold_match = re.search(r"(\d+)", sold_text.replace(".", ""))
            sold = int(sold_match.group(1)) if sold_match else 0

            products.append({
                "name": name,
                "price": price,
                "sold": sold,
                "link": link
            })
        except Exception as e:
            st.warning(f"Unable to fetch Tokopedia data: {str(e)}")

    driver.quit()

    # filter produk yang sold > 0
    filtered = [p for p in products if p["sold"] > 0]

    if not filtered:
        return None

    # ambil produk dengan harga tertinggi
    highest = max(filtered, key=lambda x: x["price"])
    
    # return URL saja karena itu yang dibutuhkan untuk scraping detail produk
    return highest["link"]

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
    tokopedia_url = scrape_tokopedia_search(product_name)
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


    # Search for product in knowledge base
    summary_solution_data = None
    kb = load_knowledge_base()
    for product in kb['products']:
        if product_name.lower() in product['product_name'].lower():
            summary_solution_data = {
                "name": product['product_name'],
                "price": float(product['nett_price']),
                "platform": product['platform'],
                "url": product['url']
            }
            summary_solution_data['price'] *= (1 + margin)  # Apply margin
            break
    

    # Bandingkan harga dan pilih yang tertinggi
    max_price_data = None
    if tokopedia_data and shopee_data and summary_solution_data:
        max_price_data = tokopedia_data if tokopedia_data['price'] > shopee_data['price'] and tokopedia_data['price'] > summary_solution_data['price'] else shopee_data if shopee_data['price'] > summary_solution_data['price'] else summary_solution_data
    elif tokopedia_data:
        max_price_data = tokopedia_data
    elif shopee_data:
        max_price_data = shopee_data
    elif summary_solution_data:
        max_price_data = summary_solution_data

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

def extract_evaluation_from_response(response_text):
    """Extract evaluation details from assistant's response"""
    try:
        products = []
        lines = response_text.split('\n')
        current_product = {}
        
        for line in lines:
            line = line.strip()
            if "Product:" in line or "Produk:" in line:
                if current_product:
                    products.append(current_product)
                current_product = {}
                current_product['product_name'] = line.split(":", 1)[1].strip()
            elif "Quantity:" in line or "Jumlah:" in line:
                current_product['quantity'] = int(line.split(":", 1)[1].strip())
            elif "Unit Price:" in line or "Harga Satuan:" in line:
                price_str = line.split(":", 1)[1].strip()
                price_str = price_str.replace("Rp", "").replace(".", "").replace(",", "").strip()
                current_product['unit_price'] = float(price_str)
            elif "Total Price:" in line or "Total Harga Penawaran:" in line:
                total_price_str = line.split(":", 1)[1].strip()
                total_price_str = total_price_str.replace("Rp", "").replace(".", "").replace(",", "").strip()
                current_product['total_price'] = float(total_price_str)
        
        if current_product:
            products.append(current_product)
        
        return products
    except Exception as e:
        st.error(f"Error extracting evaluation data: {str(e)}")
        return None


def evaluate_vendor_offerings(response_text, margin):
    """Evaluate vendor offerings and create Excel file"""
    try:
        # Extract product information from response
        products = extract_evaluation_from_response(response_text)
        if not products:
            return None
            
        # Create Excel data
        excel_data = create_evaluation_excel(products, margin)
        if not excel_data:
            return None
            
        # Generate Excel file
        return download_business_offering(excel_data)
    except Exception as e:
        st.error(f"Error in evaluation process: {str(e)}")
        return None

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

st.set_page_config(page_title="Pricing Chatbot for Solution Team", page_icon="🤖", layout="wide")
st.title("AI Chatbot App for Solution Team")
st.write("This is a chatbot app using Google Gemini AI for estimating best pricing of CPE items.")

# Initialize the Generative AI model
model = genai.GenerativeModel('gemini-1.5-flash')

ROLE = {
        "Price Researcher": {
            "system_prompt": """Kamu adalah seorang peneliti harga dengan tugas sebagai berikut:

1. PENCARIAN HARGA:
   - SELALU periksa dan gunakan data dari knowledge base TERLEBIH DAHULU
   - Jika ada data yang cocok di knowledge base, berikan informasi tersebut sebagai referensi utama
   - Jika tidak ada data yang cocok persis, berikan saran dari informasi yang relevan terutama yang bersumber dari e-commerce
   - Untuk platform e-commerce, cari data real-time sebagai perbandingan

2. PENGGUNAAN KNOWLEDGE BASE:
   - SELALU periksa knowledge base terlebih dahulu
   - Jika query terlalu umum, tampilkan semua produk relevan dari knowledge base
   - Jika perlu detail tambahan, mulai dengan menunjukkan data yang tersedia
   - Berikan panduan spesifik berdasarkan data di knowledge base
   - Baru kemudian tanyakan detail tambahan jika diperlukan
   
3. ASUMSI TEKNIS:
   - Hindari terlalu banyak bertanya tentang spesifikasi teknis
   - Gunakan asumsi spesifikasi sesuai rekomendasi profesional
   - Fokus pada perbandingan harga, bukan detail teknis

3. REFERENSI:
   - Sertakan link referensi untuk setiap harga yang direkomendasikan
   - Prioritaskan link dari knowledge base jika tersedia
   - Cantumkan platform sumber untuk setiap harga

4. FORMAT LAPORAN:
   - Berikan format poin yang berisi nama produk, harga, link referensi, dan justifikasi
   - Tampilkan harga dalam format yang jelas (contoh: Rp 1.000.000)
   - Rekomendasi harga terbaik adalah harga tertinggi yang memiliki rating paling banyak atau seminimalnya 1 rating
   - Berikan justifikasi singkat untuk setiap rekomendasi""",
            "icon": "💰",
            "description": "Sebagai peneliti harga, saya akan mencari dan membandingkan harga produk dari berbagai sumber untuk memberikan rekomendasi harga terbaik."
        },
        "Offering Reviewer": {
            "system_prompt": """Kamu adalah seorang reviewer penawaran harga dengan tugas sebagai berikut:

1. ANALISIS PENAWARAN:
   - Tinjau penawaran harga dari vendor secara menyeluruh
   - Bandingkan dengan harga pasar di platform e-commerce
   - Evaluasi kewajaran harga berdasarkan harga dari knowledge base dikali margin.
   - Cara Evaluasi:
       1. Harga dari knowledge base merupakan harga satuan
       2. Hitung harga wajar mitra dengan mengalikan harga dari knowledge base dengan margin.
       3. Jika harga penawaran lebih tinggi dibandingkan harga dari knowledge base dikali margin, maka status penawaran harga tidak wajar
       4. Jika harga penawaran lebih rendah dibandingkan harga dari knowledge base dikali margin, maka status penawaran harga wajar.

2. PERSYARATAN PELANGGAN:
   - Pastikan penawaran memenuhi semua persyaratan pelanggan
   - Identifikasi gap antara penawaran dan kebutuhan
   - Berikan saran penyesuaian jika diperlukan

3. ANALISIS KOMPETITIF:
   - Bandingkan dengan harga kompetitor di pasar
   - Evaluasi value proposition penawaran
   - Pertimbangkan faktor diferensiasi

4. REKOMENDASI:
   - Berikan rekomendasi penerimaan/penolakan penawaran
   - Sarankan poin negosiasi jika diperlukan
   - Sertakan justifikasi untuk setiap rekomendasi""",
            "icon": "📄",
            "description": "Sebagai reviewer penawaran, saya akan mengevaluasi dan memberikan masukan tentang penawaran harga yang diajukan oleh vendor."
        },
    }


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

    # --- Sidebar Platform Selection ---
    #st.subheader("🛒 Platform Selection")
    #st.write("You can select multiple platforms to compare prices.")
    selected_platform = ["Summary Solution"] #st.multiselect(
        #"Select Platform",
        #["Tokopedia", "Shopee", "Summary Solution"],
        #default=["Summary Solution"]
    

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
    
    # Initialize knowledge base in session state if not exists
    if "knowledge_base" not in st.session_state:
        kb_data = load_knowledge_base()
        st.session_state.knowledge_base = kb_data
        if kb_data['products']:
            st.success("Knowledge base loaded successfully!")
        else:
            st.warning("Knowledge base is empty or not found. Starting with empty knowledge base.")
    
    # Display current knowledge base
    if "knowledge_base" in st.session_state and st.session_state.knowledge_base.get('products'):
        st.write("Knowledge Base Reference:")
        try:
            # Convert dictionary format to DataFrame with explicit columns
            kb_df = pd.DataFrame(st.session_state.knowledge_base['products'])
            # Ensure column names match exactly with Excel file
            kb_df = kb_df.rename(columns={
                'product_name': 'Product Name',
                'nett_price': 'Price',
                'platform': 'Platform',
                'url': 'URL'
            })
            if not kb_df.empty:
                # Format price column
                kb_df['Price'] = kb_df['Price'].apply(lambda x: f"Rp {int(float(x)):,}")
                # Display with better formatting
                st.dataframe(
                    kb_df,
                    column_config={
                        "URL": st.column_config.LinkColumn(),
                        "Price": st.column_config.TextColumn(width="medium"),
                        "Product Name": st.column_config.TextColumn(width="medium"),
                        "Platform": st.column_config.TextColumn(width="small"),
                    },
                    hide_index=True,
                )


            # Add download button with better styling
            kb_data = download_knowledge_base()
            if kb_data:
                st.download_button(
                    label="Download Knowledge Base",
                    data=kb_data,
                    file_name="knowledge_base.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except Exception as e:
            st.error(f"Error displaying knowledge base: {str(e)}")

    if st.button("Update Knowledge Base"):
        #Refresh display current knowledge base
        st.session_state.knowledge_base = load_knowledge_base()
        st.success("Knowledge base updated!")
        #Display update knowledge base above
        st.rerun()
    
    # Add new knowledge from chat
    if st.button("Add Knowledge from Chat"):
        if st.session_state.messages and len(st.session_state.messages) > 0:
            # Get last chat message
            last_message = st.session_state.messages[-1]["content"]
            
            try:
                from price_researcher import extract_product_name, extract_price
                
                # Extract product name
                product_name = extract_product_name(last_message)
                print(product_name)

                # Extract price
                price = extract_price(last_message)
                
                # Extract link
                link_pattern = r"https?://[^\s<>\"']+"
                link_match = re.search(link_pattern, last_message)
                link = link_match.group(0) if link_match else None
                
                # Check platform from link
                platform = None
                if link:
                    if "tokopedia" in link.lower():
                        platform = "Tokopedia"
                    elif "shopee" in link.lower():
                        platform = "Shopee"
                    else:
                        platform = "Summary Solution"

                if price and platform and link and product_name:
                    try:
                        
                        # Create product info
                        product_data = {
                            'name': product_name,
                            'price': price,
                            'platform': platform,
                            'url': link
                        }
                        
                        # Save to knowledge base
                        if save_to_knowledge_base(product_data):
                            # Reload knowledge base to session state
                            st.session_state.knowledge_base = load_knowledge_base()
                            st.success("Product information added to knowledge base!")
                        
                    except ValueError as e:
                        st.error(f"Error converting price: {str(e)}")
                else:
                    missing = []
                    if not product_name: missing.append("product name")
                    if not price: missing.append("price")
                    if not platform: missing.append("platform")
                    if not link: missing.append("link")
                    st.warning(f"Could not extract complete product information. Missing: {', '.join(missing)}")
            except Exception as e:
                st.error(f"Error processing message: {str(e)}")

    # Logic to upload offerings
    st.header("📤 Upload Offerings")
    # Add button to download offering template
    excel_data = create_offering_template()
    if excel_data:
        st.download_button(
            label="Download Offering Template",
            data=excel_data,
            file_name="offering_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    uploaded_file = st.file_uploader("Upload Offerings (Excel file)", type=["xlsx"])
    if uploaded_file is not None:
        # Process the uploaded file
        business_offering = extract_text_from_excel(uploaded_file)

    # Add Evaluate Last Response button if there are messages
    if st.session_state.messages and len(st.session_state.messages) > 0:
        last_message = st.session_state.messages[-1]
        if selected_role == "Offering Reviewer":
            st.button("Extract Evaluation Results", disabled=True)
            #st.write("This feature is still under development.")
            st.markdown("<p style='color: red; font-size: 12px;'>This feature is still under development.</p>", unsafe_allow_html=True)
            

# Update session state based on current selections
if selected_role and st.session_state.current_role != selected_role:
    st.session_state.current_role = selected_role
    welcome_message = f"**{selected_role} {ROLE[selected_role]['icon']}**: {ROLE[selected_role]['description']}"
    st.session_state.messages.append({"role": "assistant", "content": welcome_message})
    
if selected_project and st.session_state.current_project != selected_project:
    st.session_state.current_project = selected_project

# Atur ulang percakapan jika project berganti
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
        
        # Tambahkan nama proyek ke dalam prompt sistem
        system_prompt += f"\n\n=== PROJECT NAME ===\n{selected_project}"

        # Extract product name from query
        product_name = extract_product_name(prompt)

        # Tambahkan nama produk ke dalam prompt sistem jika ditemukan
        if product_name:
            system_prompt += f"\n\n=== PRODUCT NAME ===\n{product_name}"
            #print(f"Extracted product name: {product_name}")

        # Tambahkan konteks dari berbagai sumber
        context_info = []
        
        # Tambahkan informasi dari knowledge base jika tersedia
        if "knowledge_base" in st.session_state and st.session_state.knowledge_base.get('products', []):
            if product_name:
                # Cari produk yang cocok di knowledge base
                matching_products = [
                    p for p in st.session_state.knowledge_base['products']
                    if product_name.lower() in p['product_name'].lower()
                ]
                if matching_products:
                    context_info.append("""
                    KNOWLEDGE BASE INFORMATION:
                    Ditemukan produk yang sesuai dalam knowledge base:
                    """)
                    for p in matching_products:
                        context_info.append(f"""
                        Nama: {p['product_name']}
                        Harga: Rp {float(p['nett_price']):,.2f}
                        Platform: {p['platform']}
                        URL: {p['url']}
                        ---
                        """)
                    print(f"Found {len(matching_products)} matching products in knowledge base.")
                else:
                    # Jika tidak ada yang cocok persis, tampilkan semua data sebagai referensi
                    kb_info = format_knowledge_base(st.session_state.knowledge_base)
                    context_info.append(f"""
                    KNOWLEDGE BASE INFORMATION:
                    Tidak ditemukan produk yang persis sama. Berikut semua data yang tersedia:
                    {kb_info}
                    """)
                    print("No exact match found in knowledge base. Displaying all available data.")

        # Tambahkan informasi dari platform e-commerce yang dipilih
        for platform in selected_platform:
            if platform == "Summary Solution" and product_name:
                if "knowledge_base" in st.session_state and st.session_state.knowledge_base.get('products'):
                    matching_products = [
                        p for p in st.session_state.knowledge_base['products']
                        if product_name.lower() in p['product_name'].lower()
                    ]
                    if matching_products:
                        context_info.append("""
                        SUMMARY SOLUTION INFORMATION:
                        Found the following matching products in knowledge base:
                        """)
                        for p in matching_products:
                            context_info.append(f"""
                            Product: {p['product_name']}
                            Price: Rp {float(p['nett_price']):,.2f}
                            Platform: {p['platform']}
                            URL: {p['url']}
                            ---
                            """)
                    else:
                        context_info.append("""
                        SUMMARY SOLUTION INFORMATION:
                        No matching products found in knowledge base.
                        """)
            elif platform == "Shopee":
                try:
                    shopee_url = find_shopee_product_url(product_name)
                    if shopee_url:
                        product_data = scrape_shopee_product_page(shopee_url)
                        if product_data:
                            context_info.append(f"""
                            SHOPEE PRODUCT INFORMATION:
                            Product: {product_data['name']}
                            Price: Rp {product_data['price']:,.2f}
                            Reviews: {product_data['reviews_count']}
                            URL: {product_data['url']}
                            """)
                except Exception as e:
                    st.warning(f"Unable to fetch Shopee data: {str(e)}")
                    
            elif platform == "Tokopedia":
                try:
                    tokopedia_url = scrape_tokopedia_search(product_name)
                    if tokopedia_url:
                        product_data = scrape_tokopedia_product_page(tokopedia_url)
                        print(product_data)
                        if product_data:
                            context_info.append(f"""
                            TOKOPEDIA PRODUCT INFORMATION:
                            Product: {product_data['name']}
                            Price: Rp {product_data['price']:,.2f}
                            Rating Count: {product_data['rating_count']}
                            URL: {product_data['url']}
                            """)
                except Exception as e:
                    st.warning(f"Unable to fetch Tokopedia data: {str(e)}")
                

        # Gabungkan semua informasi konteks
        if context_info:
            system_prompt += f"""

            IMPORTANT CONTEXT INFORMATION:
            
            {' '.join(context_info)}

            When answering:
            1. Please prioritize and take information from KNOWLEDGE BASE INFORMATION when available. Please ensure to give confirmation to user whether it's available or not
            2. Use live data from selected e-commerce platforms for current market comparison
            3. Always include relevant product links from all available sources
            4. Compare prices between knowledge base and current market data
            5. Consider platform-specific factors (ratings, reviews, seller reputation)
            6. Highlight any significant price differences between platforms
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
            if hasattr(chunk, "text") and chunk.text:
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