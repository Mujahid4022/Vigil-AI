"""
scraper.py - Automatically finds a product link on a homepage and extracts real product data.
"""
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def extract_product_from_url(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        response = requests.get(url, timeout=15, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Extract Product Name (Title)
        product_name = None
        og_title = soup.find('meta', property='og:title')
        h1 = soup.find('h1')
        html_title = soup.find('title')
        
        if og_title and og_title.get('content'):
            product_name = og_title['content']
        elif h1:
            product_name = h1.get_text(strip=True)
        elif html_title:
            product_name = html_title.get_text(strip=True)
            
        if not product_name:
            product_name = "Product Not Found"
            
        # 2. Extract Price
        price = None
        price_regex = re.compile(r'(Rs\.|PKR|Rs)\s?([\d,]+\.?\d*)')
        price_text = soup.find(string=price_regex)
        if price_text:
            match = price_regex.search(price_text)
            if match:
                price = match.group(0)
        if not price:
            price_tag = soup.find(class_=re.compile(r'price|amount|currency|Price'))
            if price_tag:
                price = price_tag.get_text(strip=True)[:20]
        price = price if price else "Check Price on Site"

        # 3. Extract Image URL
        image_url = None
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = og_image['content']
        else:
            img_tag = soup.find('img', {'src': re.compile(r'\.(jpg|jpeg|png|webp)')})
            if img_tag and img_tag.get('src'):
                img_src = img_tag['src']
                if img_src.startswith('//'):
                    img_src = 'https:' + img_src
                elif img_src.startswith('/'):
                    img_src = urljoin(url, img_src)
                image_url = img_src

        # 4. Extract Product Description
        detail = None
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            detail = og_desc['content'][:150] + "..."
        else:
            first_p = soup.find('p')
            if first_p:
                raw_text = first_p.get_text(strip=True)
                if len(raw_text) > 20:
                    detail = raw_text[:150] + "..."
        detail = detail if detail else "Check full details on the seller's website."

        # 5. Seller name from domain
        domain = urlparse(url).netloc.replace("www.", "")
        seller = domain.split('.')[0].capitalize() if domain else "Online Store"

        return {
            'product': product_name[:150],
            'price': price,
            'image_url': image_url,
            'link': url,
            'detail': detail,
            'seller': seller,
        }
    except Exception as e:
        print(f"⚠️ Error scraping product URL {url}: {e}")
        return None

def scrape_deals(url):
    """
    Scrapes a homepage, finds a product link, and fetches the real product details.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=15, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        # --- Step 1: Find a product link on the homepage ---
        product_links = []
        # Look for common product URL patterns
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # Detect typical e-commerce product link patterns
            if (re.search(r'/(product|item|p|products|deal|offer)/', href, re.IGNORECASE) or 
                re.search(r'\d+\.html', href) or 
                ('product' in a_tag.get('class', []) or 'item' in a_tag.get('class', []))):
                full_url = urljoin(url, href)
                if full_url not in product_links:
                    product_links.append(full_url)

        # --- Step 2: If a product link is found, go inside and scrape it ---
        if product_links:
            target_product_url = product_links[0]  # Take the first valid product link
            print(f"🔗 Found a product link! Scraping: {target_product_url}")
            return extract_product_from_url(target_product_url)
        
        # --- Step 3: Fallback (If no product link found, just scrape the homepage) ---
        print("⚠️ No product link found on homepage. Falling back to homepage scrape.")
        return extract_product_from_url(url)

    except Exception as e:
        print(f"⚠️ Error scraping initial URL {url}: {e}")
        return {
            'product': "Check out this deal!",
            'price': "Limited Time Offer",
            'image_url': None,
            'link': url,
            'detail': "Visit website for more details.",
            'seller': "Online Store",
        }