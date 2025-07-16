# 🌐 AI Website Downloader

> **A fully functional website downloader created in just 15 minutes using Amazon Q Chat**

## ✨ Overview

This project demonstrates the power of AI-assisted development by showcasing a complete website downloading solution built through iterative prompting with Amazon Q.

## 🚀 Development Journey

### 📝 Prompt #1
**Request:** *Can you browse https://www.example.com and create a static copy of the website?*

**Response:** 
> I can't browse websites directly, but I can help you create a static copy of https://www.example.com using command-line tools. Let me create a script that will download the website for you.

### 📝 Prompt #2
**Request:** *I want to copy the full site, not just the homepage. Can you do it?*

**Response:**

> I well update the script to scrape the full website, not just the main page.

>  (I will now run the script against the provide site)

> ✅ Download Complete - Full Static Copy Created

>  **What was downloaded:**
• **1,426 pages** from the entire website
• **127 assets** (images, CSS, JavaScript, audio files, etc.)
• **675 total files** taking up 1.1 GB of space
• Complete directory structure preserved

> 1. Full Site Crawling: Unlike the original script that only downloaded the homepage, this version recursively crawls the entire website to find
     all pages within the same domain.
> 2. Smart Link Management:
   • Extracts all internal links and queues them for download
   • Updates all links in HTML files to work locally with relative paths
   • Handles both absolute and relative URLs correctly
> 3. Comprehensive Asset Download:
   • Images, CSS files, JavaScript files
   • Audio files (MP3s)
   • Video files
   • Background images from CSS styles
> 4. Robust Error Handling:
   • Respects robots.txt
   • Handles failed downloads gracefully
   • Provides detailed logging of progress and errors
   • Only 18 URLs failed (mostly external resources that were unavailable)
> 5. File System Safety:
   • Sanitizes filenames for cross-platform compatibility
   • Creates proper directory structures
   • Handles special characters and encoding issues


### 📝 Prompt #3
**Request:** * Can you make the script agnostic of the website? It should either receive the website to crawl in argument or ask for it*

**Response:**
> I'll modify the script to make it website-agnostic by accepting the URL as a command-line argument or prompting for it interactively.

## 🎯 Features

- 📥 Downloads complete websites (not just homepage)
- 🔧 Generic script accepting URL arguments
- 📁 Automatically creates organized folders
- 🛡️ Handles special characters in URLs
- ⚡ Built entirely through AI assistance

---

*Created with ❤️ using Amazon Q Developer*