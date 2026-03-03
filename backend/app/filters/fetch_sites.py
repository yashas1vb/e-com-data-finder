import requests
import csv
import time
import os
from typing import List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SiteFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://serpapi.com/search"
        self.session = requests.Session()
        self.rate_limit_delay = 1  # Delay between requests in seconds

    def fetch_relevant_sites(self, keyword: str, country: str = "", location: str = "", result_count: int = 50) -> List[str]:
        """
        Fetch relevant sites based on search criteria.
        
        Args:
            keyword: Main search keyword
            country: Country to search in
            location: City or state to search in
            result_count: Number of results to fetch
            
        Returns:
            List of website URLs
        """
        if not self.api_key:
            raise ValueError("API key is required")

        query = self._build_query(keyword, country, location)
        logger.info(f"Querying Google for: {query}")

        params = {
            "engine": "google",
            "q": query,
            "api_key": self.api_key,
            "num": 100  # Google caps at 100 per page
        }

        all_links = set()
        start = 0
        max_retries = 3

        while len(all_links) < result_count:
            params["start"] = start
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    response = self.session.get(self.base_url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    
                    # Check for API errors
                    if "error" in data:
                        error_msg = data.get("error", "Unknown API error")
                        logger.error(f"API Error: {error_msg}")
                        raise ValueError(f"API Error: {error_msg}")
                    
                    results = data.get("organic_results", [])
                    if not results:
                        logger.info("No more results found")
                        return list(all_links)

                    for result in results:
                        link = result.get("link")
                        if link and self._is_valid_url(link) and link not in all_links:
                            all_links.add(link)
                        if len(all_links) >= result_count:
                            return list(all_links)

                    start += 10  # next page
                    time.sleep(self.rate_limit_delay)  # Rate limiting
                    break  # Success, exit retry loop
                    
                except requests.RequestException as e:
                    retry_count += 1
                    logger.error(f"Request failed (attempt {retry_count}/{max_retries}): {str(e)}")
                    if retry_count == max_retries:
                        logger.error("Max retries reached, stopping fetch")
                        return list(all_links)
                    time.sleep(self.rate_limit_delay * 2)  # Increased delay on retry

        return list(all_links)

    def _build_query(self, keyword: str, country: str, location: str) -> str:
        """Build the search query string."""
        query_parts = [f'"{keyword}"', 'site:.com']
        if country:
            query_parts.append(f'"{country}"')
        if location:
            query_parts.append(f'"{location}"')
        return ' '.join(query_parts)

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        return url.startswith(('http://', 'https://')) and '.' in url

def save_to_csv(url_list: List[str], filename: str) -> None:
    """Save URLs to a CSV file."""
    try:
        with open(filename, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Website URL"])
            for url in url_list:
                writer.writerow([url])
        logger.info(f"Saved {len(url_list)} URLs to {filename}")
    except IOError as e:
        logger.error(f"Failed to save CSV file: {str(e)}")
        raise

def fetch_sites(keyword: str, country: str, city: str, count: int, output_file: str) -> None:
    """
    Main function to fetch sites and save to CSV.
    
    Args:
        keyword: Search keyword
        country: Country to search in
        city: City to search in
        count: Number of results to fetch
        output_file: Path to save the CSV file
    """
    try:
        # Get API key from environment variable or use default
        API_KEY = os.getenv('SERPAPI_KEY', '7d2d780a5220ceb67153834a34d7791806989772a5fcd4d9101b2a31b27bd998')
        
        fetcher = SiteFetcher(API_KEY)
        sites = fetcher.fetch_relevant_sites(keyword, country, city, count)
        
        if sites:
            save_to_csv(sites, output_file)
            logger.info(f"Successfully fetched {len(sites)} sites")
        else:
            logger.warning("No sites found matching the criteria")
            raise ValueError("No sites found matching the criteria")
            
    except Exception as e:
        logger.error(f"Error in fetch_sites: {str(e)}")
        raise

__all__ = ['fetch_sites']

if __name__ == "__main__":
    keyword = "example"
    country = "United States"
    city = "New York"
    count = 50
    output_file = "relevant_sites.csv"
    logger.info(f"Starting to fetch sites for keyword: {keyword}, country: {country}, city: {city}, count: {count}")
    fetch_sites(keyword, country, city, count, output_file)
    logger.info(f"Sites fetched and saved to {output_file}")
