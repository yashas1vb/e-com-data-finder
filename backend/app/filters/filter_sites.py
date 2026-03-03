import csv
import requests
import time
import asyncio
import aiohttp
from typing import List, Dict, Set
import logging
from urllib.parse import urlparse
import concurrent.futures

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SiteFilter:
    def __init__(self, max_workers: int = 10, timeout: int = 5):
        self.max_workers = max_workers
        self.timeout = timeout
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def is_domain_active(self, url: str) -> bool:
        """Check if a domain is active using HEAD request."""
        try:
            async with self.session.head(url, timeout=self.timeout, allow_redirects=True) as response:
                return response.status < 400
        except Exception as e:
            logger.debug(f"Domain check failed for {url}: {str(e)}")
            return False

    async def is_shopify_site(self, url: str) -> bool:
        """Check if a site is built with Shopify."""
        try:
            async with self.session.get(url, timeout=self.timeout) as response:
                if response.status == 200:
                    html = await response.text()
                    html_lower = html.lower()
                    # Check for multiple Shopify indicators
                    indicators = [
                        "cdn.shopify.com",
                        "shopify",
                        "myshopify.com",
                        "shopify.com",
                        "shopifycdn.com"
                    ]
                    return any(indicator in html_lower for indicator in indicators)
                return False
        except Exception as e:
            logger.debug(f"Shopify check failed for {url}: {str(e)}")
            return False

    async def check_load_time(self, url: str, max_seconds: int) -> bool:
        """Check if a site loads within the specified time."""
        try:
            start = time.time()
            async with self.session.get(url, timeout=max_seconds) as response:
                elapsed = time.time() - start
                return response.status == 200 and elapsed <= max_seconds
        except Exception as e:
            logger.debug(f"Load time check failed for {url}: {str(e)}")
            return False

    def normalize_url(self, url: str) -> str:
        """Normalize URL format."""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url

    def is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    async def process_url(self, url: str, filters: Dict) -> bool:
        """Process a single URL with all filters."""
        url = self.normalize_url(url)
        if not self.is_valid_url(url):
            return False

        if filters.get("domain_active"):
            if not await self.is_domain_active(url):
                return False

        if filters.get("only_shopify"):
            if not await self.is_shopify_site(url):
                return False

        if filters.get("load_time"):
            if not await self.check_load_time(url, filters["load_time"]):
                return False

        return True

    async def filter_urls(self, urls: List[str], filters: Dict) -> List[str]:
        """Filter a list of URLs asynchronously."""
        tasks = []
        for url in urls:
            task = asyncio.create_task(self.process_url(url, filters))
            tasks.append((url, task))

        filtered_urls = []
        for url, task in tasks:
            try:
                if await task:
                    filtered_urls.append(url)
            except Exception as e:
                logger.error(f"Error processing {url}: {str(e)}")

        return filtered_urls

def apply_filters(input_file: str, filters: List[str], output_file: str) -> None:
    """
    Apply filters to URLs in the input CSV file and save results to output file.
    
    Args:
        input_file: Path to input CSV file
        filters: List of filter names to apply
        output_file: Path to save filtered results
    """
    try:
        # Convert filter names to filter configuration
        filter_config = {
            "domain_active": "active" in filters,
            "only_shopify": "shopify" in filters,
            "load_time": 5 if "fast" in filters else None
        }

        # Read URLs from input file
        urls = []
        with open(input_file, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            urls = [row[0].strip() for row in reader if row]

        # Process URLs
        async def process_urls():
            async with SiteFilter() as filterer:
                filtered_urls = await filterer.filter_urls(urls, filter_config)
                
                # Save results
                with open(output_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Website URL"])
                    for url in filtered_urls:
                        writer.writerow([url])
                
                logger.info(f"Filtered {len(filtered_urls)} URLs from {len(urls)} total URLs")
                return filtered_urls

        # Run async processing
        filtered_urls = asyncio.run(process_urls())
        
    except Exception as e:
        logger.error(f"Error in apply_filters: {str(e)}")
        raise

if __name__ == "__main__":
    # Example usage
    input_csv = "relevant_sites.csv"
    output_csv = "filtered_sites.csv"
    filters_to_apply = ["active", "shopify", "fast"]
    
    apply_filters(input_csv, filters_to_apply, output_csv)
