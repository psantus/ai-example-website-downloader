#!/usr/bin/env python3
"""
Universal website downloader that creates a complete static copy of any website.
This script crawls all pages within the same domain and downloads all assets.

Usage:
    python3 universal_site_downloader.py [URL] [OUTPUT_DIR] [--delay SECONDS]
    
Examples:
    python3 universal_site_downloader.py https://example.com
    python3 universal_site_downloader.py https://example.com my_site_backup
    python3 universal_site_downloader.py https://example.com my_site_backup --delay 2
"""

import requests
from bs4 import BeautifulSoup
import os
import re
import time
import sys
import argparse
from urllib.parse import urljoin, urlparse, unquote
from urllib.robotparser import RobotFileParser
import mimetypes
from pathlib import Path
import hashlib
from collections import deque
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebsiteDownloader:
    def __init__(self, base_url, output_dir, delay=1):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.output_dir = Path(output_dir)
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Track downloaded URLs and files
        self.downloaded_urls = set()
        self.downloaded_files = set()
        self.url_queue = deque([base_url])
        self.failed_urls = set()
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Check robots.txt
        self.check_robots_txt()
    
    def check_robots_txt(self):
        """Check robots.txt for crawling permissions"""
        try:
            robots_url = f"{self.base_url}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            self.robots_parser = rp
            logger.info("Robots.txt loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load robots.txt: {e}")
            self.robots_parser = None
    
    def can_fetch(self, url):
        """Check if we can fetch the URL according to robots.txt"""
        if self.robots_parser:
            return self.robots_parser.can_fetch('*', url)
        return True
    
    def sanitize_filename(self, filename):
        """Sanitize filename for filesystem compatibility"""
        # Replace invalid characters with underscores
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Remove multiple consecutive underscores and clean up
        filename = re.sub(r'_+', '_', filename)
        filename = filename.strip('. _')
        return filename[:255]  # Limit length
    
    def get_local_path(self, url):
        """Convert URL to local file path"""
        parsed = urlparse(url)
        path = unquote(parsed.path)
        
        if path == '' or path == '/':
            return self.output_dir / 'index.html'
        
        # Remove leading slash
        path = path.lstrip('/')
        
        # If path ends with /, treat as directory and add index.html
        if path.endswith('/'):
            path += 'index.html'
        elif '.' not in Path(path).name:
            # If no extension, assume it's a page and add .html
            path += '.html'
        
        # Sanitize each part of the path
        parts = [self.sanitize_filename(part) for part in path.split('/')]
        return self.output_dir / Path(*parts)
    
    def download_file(self, url, local_path):
        """Download a file from URL to local path"""
        try:
            if not self.can_fetch(url):
                logger.warning(f"Robots.txt disallows fetching: {url}")
                return False
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Create directory if it doesn't exist
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            if 'text' in response.headers.get('content-type', '').lower():
                with open(local_path, 'w', encoding='utf-8', errors='ignore') as f:
                    f.write(response.text)
            else:
                with open(local_path, 'wb') as f:
                    f.write(response.content)
            
            logger.info(f"Downloaded: {url} -> {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            self.failed_urls.add(url)
            return False
    
    def extract_links(self, soup, base_url):
        """Extract all links from HTML soup"""
        links = set()
        
        # Extract page links
        for tag in soup.find_all(['a', 'link'], href=True):
            href = tag['href']
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            # Only include links from the same domain
            if parsed.netloc == self.domain:
                # Remove fragment
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    clean_url += f"?{parsed.query}"
                links.add(clean_url)
        
        return links
    
    def extract_assets(self, soup, base_url):
        """Extract all asset URLs from HTML soup"""
        assets = set()
        
        # Images
        for img in soup.find_all('img', src=True):
            assets.add(urljoin(base_url, img['src']))
        
        # CSS files
        for link in soup.find_all('link', rel='stylesheet', href=True):
            assets.add(urljoin(base_url, link['href']))
        
        # JavaScript files
        for script in soup.find_all('script', src=True):
            assets.add(urljoin(base_url, script['src']))
        
        # Other assets (videos, audio, etc.)
        for tag in soup.find_all(['video', 'audio', 'source'], src=True):
            assets.add(urljoin(base_url, tag['src']))
        
        # Background images in style attributes
        for tag in soup.find_all(style=True):
            style = tag['style']
            urls = re.findall(r'url\(["\']?([^"\']+)["\']?\)', style)
            for url in urls:
                assets.add(urljoin(base_url, url))
        
        return assets
    
    def update_links_in_html(self, soup, original_url):
        """Update links in HTML to point to local files"""
        base_path = self.get_local_path(original_url).parent
        
        # Update page links
        for tag in soup.find_all(['a', 'link'], href=True):
            href = tag['href']
            full_url = urljoin(original_url, href)
            parsed = urlparse(full_url)
            
            if parsed.netloc == self.domain:
                local_path = self.get_local_path(full_url)
                try:
                    rel_path = os.path.relpath(local_path, base_path)
                    tag['href'] = rel_path
                except ValueError:
                    # Can't create relative path, use absolute
                    tag['href'] = str(local_path)
        
        # Update asset links
        for img in soup.find_all('img', src=True):
            src = img['src']
            full_url = urljoin(original_url, src)
            if urlparse(full_url).netloc == self.domain:
                local_path = self.get_local_path(full_url)
                try:
                    rel_path = os.path.relpath(local_path, base_path)
                    img['src'] = rel_path
                except ValueError:
                    img['src'] = str(local_path)
        
        # Update CSS links
        for link in soup.find_all('link', rel='stylesheet', href=True):
            href = link['href']
            full_url = urljoin(original_url, href)
            if urlparse(full_url).netloc == self.domain:
                local_path = self.get_local_path(full_url)
                try:
                    rel_path = os.path.relpath(local_path, base_path)
                    link['href'] = rel_path
                except ValueError:
                    link['href'] = str(local_path)
        
        # Update script sources
        for script in soup.find_all('script', src=True):
            src = script['src']
            full_url = urljoin(original_url, src)
            if urlparse(full_url).netloc == self.domain:
                local_path = self.get_local_path(full_url)
                try:
                    rel_path = os.path.relpath(local_path, base_path)
                    script['src'] = rel_path
                except ValueError:
                    script['src'] = str(local_path)
    
    def process_html_page(self, url):
        """Process an HTML page: download it and extract links"""
        if url in self.downloaded_urls:
            return
        
        try:
            if not self.can_fetch(url):
                logger.warning(f"Robots.txt disallows fetching: {url}")
                return
            
            logger.info(f"Processing HTML page: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract and queue new page links
            page_links = self.extract_links(soup, url)
            for link in page_links:
                if link not in self.downloaded_urls and link not in self.url_queue:
                    self.url_queue.append(link)
            
            # Extract and download assets
            assets = self.extract_assets(soup, url)
            for asset_url in assets:
                if asset_url not in self.downloaded_files:
                    asset_path = self.get_local_path(asset_url)
                    if self.download_file(asset_url, asset_path):
                        self.downloaded_files.add(asset_url)
            
            # Update links to point to local files
            self.update_links_in_html(soup, url)
            
            # Save the updated HTML
            local_path = self.get_local_path(url)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
            self.downloaded_urls.add(url)
            logger.info(f"Saved HTML page: {local_path}")
            
        except Exception as e:
            logger.error(f"Failed to process HTML page {url}: {e}")
            self.failed_urls.add(url)
    
    def download_website(self):
        """Main method to download the entire website"""
        logger.info(f"Starting download of {self.base_url}")
        logger.info(f"Output directory: {self.output_dir}")
        
        while self.url_queue:
            url = self.url_queue.popleft()
            
            if url in self.downloaded_urls:
                continue
            
            self.process_html_page(url)
            
            # Be respectful - add delay between requests
            if self.delay > 0:
                time.sleep(self.delay)
        
        # Summary
        logger.info(f"Download complete!")
        logger.info(f"Downloaded {len(self.downloaded_urls)} pages")
        logger.info(f"Downloaded {len(self.downloaded_files)} assets")
        
        if self.failed_urls:
            logger.warning(f"Failed to download {len(self.failed_urls)} URLs:")
            for url in list(self.failed_urls)[:10]:  # Show first 10
                logger.warning(f"  - {url}")
            if len(self.failed_urls) > 10:
                logger.warning(f"  ... and {len(self.failed_urls) - 10} more")

def validate_url(url):
    """Validate and normalize URL"""
    if not url:
        return None
    
    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Basic URL validation
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return None
        return url
    except:
        return None

def get_url_interactive():
    """Get URL from user input with validation"""
    while True:
        url = input("\nEnter the website URL to download: ").strip()
        
        if not url:
            print("Please enter a valid URL.")
            continue
        
        validated_url = validate_url(url)
        if validated_url:
            return validated_url
        else:
            print("Invalid URL format. Please enter a valid URL (e.g., https://example.com)")

def generate_output_dir(url):
    """Generate a default output directory name from URL"""
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    # Replace all special characters with underscores for directory names
    safe_domain = re.sub(r'[^a-zA-Z0-9]', '_', domain)
    # Remove multiple consecutive underscores and trailing underscores
    safe_domain = re.sub(r'_+', '_', safe_domain).strip('_')
    return safe_domain

def main():
    parser = argparse.ArgumentParser(
        description='Download a complete static copy of a website',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://example.com
  %(prog)s https://example.com my_backup
  %(prog)s https://example.com my_backup --delay 2
  %(prog)s --interactive
        """
    )
    
    parser.add_argument('url', nargs='?', help='Website URL to download')
    parser.add_argument('output_dir', nargs='?', help='Output directory (default: auto-generated from URL)')
    parser.add_argument('--delay', type=float, default=1.0, 
                       help='Delay between requests in seconds (default: 1.0)')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Interactive mode - prompt for URL and settings')
    
    args = parser.parse_args()
    
    # Interactive mode or missing URL
    if args.interactive or not args.url:
        print("=== Universal Website Downloader ===")
        print("This tool creates a complete static copy of a website.")
        
        url = get_url_interactive()
        
        # Ask for output directory
        default_output = generate_output_dir(url)
        output_input = input(f"\nOutput directory (default: {default_output}): ").strip()
        output_dir = output_input if output_input else default_output
        
        # Ask for delay
        delay_input = input(f"\nDelay between requests in seconds (default: 1.0): ").strip()
        try:
            delay = float(delay_input) if delay_input else 1.0
        except ValueError:
            delay = 1.0
            print("Invalid delay value, using default: 1.0 seconds")
    
    else:
        # Command line arguments
        url = validate_url(args.url)
        if not url:
            print(f"Error: Invalid URL '{args.url}'")
            sys.exit(1)
        
        output_dir = args.output_dir if args.output_dir else generate_output_dir(url)
        delay = args.delay
    
    # Confirm settings
    print(f"\n=== Download Settings ===")
    print(f"URL: {url}")
    print(f"Output directory: {output_dir}")
    print(f"Delay between requests: {delay} seconds")
    
    # Check if output directory exists
    if os.path.exists(output_dir):
        response = input(f"\nOutput directory '{output_dir}' already exists. Overwrite? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("Download cancelled.")
            sys.exit(0)
        
        # Remove existing directory
        import shutil
        shutil.rmtree(output_dir)
    
    print(f"\nStarting download...")
    
    try:
        downloader = WebsiteDownloader(url, output_dir, delay)
        downloader.download_website()
        
        print(f"\n=== Download Complete! ===")
        print(f"Static copy saved to: {output_dir}")
        print(f"Open {output_dir}/index.html in your browser to view the site")
        
    except KeyboardInterrupt:
        print(f"\n\nDownload interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during download: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
