# Vigil AI Bot

A modular, automated desktop application for managing and scheduling content on Facebook Pages. 
Supports multiple AI providers (Gemini, Groq, OpenAI, Anthropic, Mistral, DeepSeek) and automated 
content generation based on user-defined instructions.

## Features
- **Multi-Page Management:** Add and manage multiple Facebook Pages from a single dashboard.
- **Universal AI Integration:** Choose your preferred AI provider for text generation. Supports Gemini, Groq, OpenAI, DeepSeek, Anthropic, and Mistral.
- **Automated Scheduling:** Schedule posts to run every X hours for each page individually.
- **URL Scraping & Deal Hunting:** Scrape user-provided URLs to find deals, news, or updates.
- **Image Generation:** Automatically generates images for poetry/promotional posts (with fallback to Pollinations.ai).
- **Language Support:** Supports Urdu, English, both, or auto-detect based on the page brief.

## Getting Started

### Prerequisites
- Windows OS
- [Python 3.10+](https://www.python.org/downloads/)
- API keys for your preferred AI provider (Gemini/Groq/OpenAI/etc.)
- A Facebook Developer App (for generating Page Access Tokens)

### Installation
1. Download and extract the `Vigil_AI_Bot.zip` file (or download the source code).
2. Open a PowerShell terminal in the extracted folder.
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
