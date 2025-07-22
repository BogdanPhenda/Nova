# Catalog Bot

A Python-based bot for automated catalog management using Google Sheets and XML feed generation.

## Features

- Automated catalog data processing from Google Sheets
- XML feed generation for product catalogs
- S3 storage integration for feed files
- Asynchronous file handling
- FastAPI-based web interface

## Prerequisites

- Python 3.8+
- Google Sheets API credentials
- AWS S3 credentials
- Access to required Google Spreadsheets

## Installation

1. Clone the repository:
```bash
git clone <your-repository-url>
cd catalog-bot2
```

2. Create and activate virtual environment:
```bash
python -m venv venv
# For Windows
venv\Scripts\activate
# For Unix/MacOS
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up configuration:
   - Create `google-credentials.json` with your Google API credentials
   - Configure environment variables:
     ```
     AWS_ACCESS_KEY_ID=your_access_key
     AWS_SECRET_ACCESS_KEY=your_secret_key
     AWS_DEFAULT_REGION=your_region
     SPREADSHEET_ID=your_spreadsheet_id
     ```

## Project Structure

```
catalog-bot2/
├── bot/            # Bot core functionality
├── feed/           # Feed generation logic
├── google_sheets/  # Google Sheets integration
├── uploads/        # Temporary storage for generated feeds
└── s3_async_client.py  # S3 client implementation
```

## Usage

1. Start the bot:
```bash
python main.py
```

2. The bot will:
   - Fetch data from configured Google Sheets
   - Generate XML feed files
   - Upload feeds to S3 storage
   - Provide API endpoints for manual operations

## API Endpoints

- `GET /health` - Check service health
- `POST /generate-feed` - Manually trigger feed generation
- `GET /feeds` - List available feeds

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 