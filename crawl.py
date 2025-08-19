from crawlbase import CrawlingAPI
from bs4 import BeautifulSoup
import json

# Initialize Crawlbase API with your token
crawling_api = CrawlingAPI({ 'token': 'yiXb5P4RU8PUjNFim7gIxA' })

# Function to scrape Tokopedia product page
def scrape_product_page(url):
    options = {
        'ajax_wait': 'true',
        'page_wait': '5000'
    }
    response = crawling_api.get(url, options)

    if response['headers']['pc_status'] == '200':
        html_content = response['body'].decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')

        # Extracting Product Data
        product_data = {}
        product_data['name'] = soup.select_one('h1[data-testid="lblPDPDetailProductName"]').text.strip()
        product_data['price'] = soup.select_one('div[data-testid="lblPDPDetailProductPrice"]').text.strip()
        product_data['store_name'] = soup.select_one('a[data-testid="llbPDPFooterShopName"]').text.strip()
        product_data['description'] = soup.select_one('div[data-testid="lblPDPDescriptionProduk"]').text.strip()
        product_data['images_url'] = [img['src'] for img in soup.select('button[data-testid="PDPImageThumbnail"] img.css-1c345mg')]

        return product_data
    else:
        print(f"Failed to fetch the page. Status code: {response['headers']['pc_status']}")
        return None

# Function to store scraped data in a JSON file
def store_data_in_json(data, filename='tokopedia_product_data.json'):
    with open(filename, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    print(f"Data stored in {filename}")