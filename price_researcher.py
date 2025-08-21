import re

def extract_product_name(prompt):
    """
    Extract product name from user prompt using various patterns
    
    Args:
        prompt (str): User message/prompt
        
    Returns:
        str: Extracted product name or None if not found
    """
    # List of possible trigger phrases in Indonesian and English
    triggers = [
        r"(?:berapa harga|harga dari|harga|price of|cek harga|check price of|cari harga|search price for)\s+(?:produk |product |barang |item |jasa |service )?(?P<name>[^?.,!]*)",
        r"(?:cari|search for|find|tolong carikan|please find)\s+(?:produk |product |barang |item |jasa |service )?(?P<name>[^?.,!]*)",
        r"(?:beli|purchase|buy|ingin membeli|want to buy)\s+(?P<name>[^?.,!]*)",
        r"(?:dari)\s+(?P<name>[^?.,!]*)"  # Menangkap pattern "dari [product]"
    ]
    
    prompt = prompt.lower().strip()
    
    # Try each pattern
    for pattern in triggers:
        match = re.search(pattern, prompt)
        if match:
            name = match.group("name").strip()
            if name:  # Make sure we got something meaningful
                return name

    # If no pattern matches, try finding product name after "Product:" or "Nama Produk:"
    if "product:" in prompt:
        name = prompt.split("product:")[-1].split("\n")[0].strip()
        return name
    elif "nama produk:" in prompt:
        name = prompt.split("nama produk:")[-1].split("\n")[0].strip()
        return name
        
    return None

def extract_price(text):
    """
    Extract price from text
    
    Args:
        text (str): Text containing price information
        
    Returns:
        float: Extracted price or None if not found
    """
    # Price patterns with currency
    patterns = [
        r'(?:Rp\.?|IDR)\s*(\d{1,3}(?:\.\d{3})*(?:\,\d+)?)',  # Format: Rp 1.234.567,89 or IDR 1.234.567,89
        r'(?:Rp\.?|IDR)\s*(\d+)'  # Simple format: Rp 1234567 or IDR 1234567
    ]
    
    text = text.strip()
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            # Extract the numeric part
            price_str = match.group(1)
            # Remove thousand separators and replace decimal comma with dot
            price_str = price_str.replace(".", "").replace(",", ".")
            try:
                return float(price_str)
            except ValueError:
                continue
                
    return None
