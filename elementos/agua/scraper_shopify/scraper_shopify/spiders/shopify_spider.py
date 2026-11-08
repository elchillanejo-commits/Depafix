import scrapy
import json

class ShopifySpider(scrapy.Spider):
    name = "shopify"
    
    def __init__(self, url=None, *args, **kwargs):
        super(ShopifySpider, self).__init__(*args, **kwargs)
        self.start_urls = [url] if url else ["https://example-shop.myshopify.com"]

    def parse(self, response):
        # 1. Extraer JSON-LD (Shopify lo usa para SEO)
        productos = response.css('script[type="application/ld+json"]::text').getall()
        for prod in productos:
            try:
                data = json.loads(prod)
                if data.get("@type") == "Product":
                    yield {
                        "nombre": data.get("name"),
                        "precio": data.get("offers", {}).get("price"),
                        "sku": data.get("sku"),
                        "url": response.url
                    }
            except:
                pass

        # 2. Paginación (siguiente página)
        next_page = response.css('a[rel="next"]::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)
