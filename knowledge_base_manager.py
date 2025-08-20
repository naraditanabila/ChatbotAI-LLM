import pandas as pd
import streamlit as st
import io

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

def get_all_platforms(knowledge_base):
    """Get list of all platforms in knowledge base"""
    platforms = set()
    for product in knowledge_base['products']:
        platforms.add(product['platform'])
    return list(platforms)

def get_price_range(knowledge_base):
    """Get min and max prices from knowledge base"""
    if not knowledge_base['products']:
        return 0, 0
    prices = [p['nett_price'] for p in knowledge_base['products']]
    return min(prices), max(prices)
