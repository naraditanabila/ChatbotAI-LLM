from main import scrape_tokopedia_search

queries = [
    "Ruijie Reyee RG-RAP2200",
    "RG-RAP2200",
    "Ruijie Access Point"
]

print("Testing scrape_tokopedia_search with multiple queries...")
for query in queries:
    print(f"\nQuery: {query}")
    result = scrape_tokopedia_search(query)
    print(f"Result URL: {result}")
