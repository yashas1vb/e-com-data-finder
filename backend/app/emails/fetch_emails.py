import csv
import re
import requests
from urllib.parse import urlparse, urljoin
import concurrent.futures
import time
import logging
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("email_extraction.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def extract_emails_from_text(text):
    """Extract email addresses from text using a more comprehensive regex pattern."""
    # More comprehensive email regex pattern
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    # Find all matches
    emails = re.findall(email_pattern, text)
    
    # Filter out common false positives and invalid emails
    filtered_emails = []
    for email in emails:
        # Skip emails with invalid characters after the @ symbol
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            continue
        
        # Skip emails with common placeholders
        if any(placeholder in email.lower() for placeholder in ['example', 'yourname', 'youremail', 'username', 'domain']):
            continue
            
        filtered_emails.append(email)
    
    return filtered_emails

def create_session():
    """Create a requests session with retry capability."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def normalize_url(url):
    """Normalize URL by adding scheme if missing."""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url

def fetch_emails_from_url(url):
    """Fetch and extract emails from a given URL and its contact page."""
    # Create a requests session with retry capability
    session = create_session()
    
    # Normalize the URL
    url = normalize_url(url)
    
    emails = []
    try:
        # User-Agent to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        logger.info(f"Fetching emails from: {url}")
        response = session.get(url, timeout=15, headers=headers)
        response.raise_for_status()
        
        # Extract emails from the main page
        page_emails = extract_emails_from_text(response.text)
        emails.extend(page_emails)
        
        # Parse domain for creating absolute URLs
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Look for contact pages
        contact_paths = ['/contact', '/contact-us', '/about', '/about-us']
        for path in contact_paths:
            try:
                contact_url = urljoin(base_url, path)
                logger.info(f"Checking contact page: {contact_url}")
                
                response = session.get(contact_url, timeout=10, headers=headers)
                if response.status_code == 200:
                    contact_emails = extract_emails_from_text(response.text)
                    emails.extend(contact_emails)
            except Exception as e:
                logger.warning(f"Failed to fetch contact page {path}: {e}")
        
        # Return unique emails
        return list(set(emails))
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unknown error with {url}: {e}")
        return []

def process_website(row, fieldnames):
    """Process a single website row and return the result."""
    # Extract website URL from various possible column names
    website = None
    for field in ['Website', 'URL', 'Domain', 'Site']:
        if field in fieldnames and row.get(field):
            website = row[field].strip()
            break
    
    # If no website found in known fields, use the first value
    if not website and row:
        website = list(row.values())[0].strip()
    
    # Skip empty websites
    if not website:
        return None, []
    
    # Fetch emails
    emails = fetch_emails_from_url(website)
    return website, emails

def fetch_emails_from_csv(input_csv_path, output_csv_path, max_workers=5):
    """
    Extract emails from websites listed in a CSV file and save results.
    
    Args:
        input_csv_path: Path to the CSV file containing websites
        output_csv_path: Path to save the extracted emails
        max_workers: Maximum number of concurrent workers
    """
    try:
        # Read the input CSV to get the fieldnames
        with open(input_csv_path, newline='', encoding='utf-8') as test_file:
            reader = csv.DictReader(test_file)
            input_fieldnames = reader.fieldnames if reader.fieldnames else []
        
        if not input_fieldnames:
            logger.error("Input CSV appears to be empty or has no headers")
            return
            
        # Create output CSV with appropriate headers
        with open(input_csv_path, newline='', encoding='utf-8-sig') as infile, \
             open(output_csv_path, 'w', newline='', encoding='utf-8-sig') as outfile:
            
            reader = csv.DictReader(infile)
            
            # Prepare output fieldnames and writer
            output_fieldnames = ['Website', 'Emails', 'Email_Count']
            writer = csv.DictWriter(outfile, fieldnames=output_fieldnames)
            writer.writeheader()
            
            # Process rows with concurrent workers
            total_sites = sum(1 for _ in infile)
            infile.seek(0)  # Reset file pointer after counting
            next(reader)  # Skip header after resetting
            
            logger.info(f"Starting email extraction from {total_sites} websites")
            
            # Process in batches to avoid memory issues with very large files
            batch_size = 100
            processed_count = 0
            
            while True:
                batch = []
                for _ in range(batch_size):
                    try:
                        row = next(reader)
                        batch.append(row)
                    except StopIteration:
                        break
                
                if not batch:
                    break
                    
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_row = {
                        executor.submit(process_website, row, input_fieldnames): row 
                        for row in batch
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_row):
                        website, emails = future.result()
                        if website:
                            processed_count += 1
                            emails_str = ', '.join(emails) if emails else ''
                            writer.writerow({
                                'Website': website,
                                'Emails': emails_str,
                                'Email_Count': len(emails)
                            })
                            
                            # Log progress periodically
                            if processed_count % 10 == 0:
                                logger.info(f"Processed {processed_count}/{total_sites} websites")
                                
                            # Add small delay to avoid overwhelming resources
                            time.sleep(0.1)
            
            logger.info(f"Email extraction completed. Processed {processed_count} websites.")
            
    except FileNotFoundError:
        logger.error(f"Input file {input_csv_path} not found")
    except Exception as e:
        logger.error(f"An error occurred during email extraction: {e}")

if __name__ == "__main__":
    input_csv = 'websites_filtered.csv'  # Your filtered sites CSV filename
    output_csv = 'emails_extracted_claude.csv'  # Output filename
    
    # Start the extraction process
    logger.info(f"Starting email extraction from {input_csv} to {output_csv}")
    fetch_emails_from_csv(input_csv, output_csv, max_workers=5)
    logger.info(f"Email extraction completed. Results saved to {output_csv}")