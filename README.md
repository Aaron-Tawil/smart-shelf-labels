# Smart Shelf Labels

Smart Shelf Labels is an automated automated signage generator for retail stores. It streamlines the process of creating professional, clean, and consistent shelf labels by integrating with email workflows and leveraging AI for content optimization.

## Features

- **Automated Workflow**: Monitors a Gmail inbox for Excel files containing product updates.
- **AI-Powered Cleaning**: Uses Google Gemini to clean up messy ERP product names into customer-friendly text (e.g., removing internal codes, fixing formatting).
- **Professional Design**: Generates high-quality PDF signage with price formatting, barcodes, and promotional "Sale" badges.
- **Smart Printing**: intelligently filters products to only print signs for new items or price changes, saving paper and ink.
- **Cloud Ready**: Designed to run as a Google Cloud Function for 24/7 automation.

## Tech Stack

- **Language**: Python 3.10+
- **Core Libraries**: 
    - `pandas` (Data processing)
    - `reportlab` (PDF generation)
    - `firebase_admin` / `google-cloud-firestore` (State management)
    - `google-generativeai` (LLM processing)
- **Infrastructure**: Google Cloud Platform (Cloud Functions, Firestore, Gmail API)

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/smart-shelf-labels.git
   cd smart-shelf-labels
   ```

2. **Install Dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Environment Configuration**
   Create an `env.yaml` file (do not commit this!) with your credentials:
   ```yaml
   GEMINI_API_KEY: 'your_api_key_here'
   GMAIL_TOKEN_JSON: '{"token": "..."}' # From Google OAuth flow
   ```

4. **Run Locally**
   ```bash
   python main.py
   ```

## Example Output

![Generated Signs Example](example/output_example_readme.png)

*Example of generated shelf labels showing clear pricing, barcodes, and product descriptions.*
