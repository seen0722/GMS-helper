# CTS Insight

A powerful web-based tool for analyzing GMS (Google Mobile Services) certification test results with AI-powered failure clustering and Redmine integration.

## Features

### 📊 Test Result Analysis
- **Multi-Suite Support**: Parse and analyze CTS, GTS, VTS, STS, and CTS-verifier test results
- **Comprehensive Reporting**: Detailed statistics, pass/fail rates, and module-level breakdowns
- **Failure Tracking**: Track individual test failures with stack traces and error messages

### 🤖 AI-Powered Clustering
- **Intelligent Grouping**: Automatically cluster similar failures using AI analysis
- **Root Cause Analysis**: Get AI-generated insights on failure patterns and common causes
- **Severity Classification**: Automatic severity and category assignment for failures

### 🔗 Redmine Integration
- **Issue Creation**: Create Redmine issues directly from failure clusters
- **Bulk Operations**: Create issues for all clusters in a single operation
- **Child Issues**: Optionally create child issues for individual test failures
- **Issue Linking**: Link clusters to existing Redmine issues

### 🎨 Modern Web Interface
- **Interactive Dashboard**: Real-time statistics and visualizations
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Search & Filter**: Quickly find specific failures or clusters
- **Export Reports**: Generate printable reports for stakeholders

## Installation

### Prerequisites
- Python 3.8+
- pip (Python package manager)

### Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd GMS-helper
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Access the application**
   Open your browser and navigate to: `http://localhost:8000`

### Docker Support

You can also run the application using Docker:

```bash
# Pull the latest image
docker pull seen0516/gms-helper:latest

# Run with Docker Compose (Recommended)
docker-compose up -d
```

Or manually with `docker run`:

```bash
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/uploads:/app/uploads \
  --name gms-helper \
  seen0516/gms-helper:latest
```

## Configuration

### OpenAI API Key (for AI Analysis)
1. Navigate to Settings in the web interface
2. Enter your OpenAI API key
3. The key is encrypted and stored securely in the database

### Redmine Integration
1. Navigate to Settings → Redmine
2. Enter your Redmine server URL (e.g., `https://redmine.example.com`)
3. Enter your Redmine API key
4. Test the connection to verify settings

## Usage

### Uploading Test Results
1. Click "Upload New Test Results" on the dashboard
2. Select your XML test result file (CTS, GTS, VTS, or STS)
3. Wait for processing to complete
4. View the analysis on the run details page

### Running AI Analysis
1. Open a test run from the dashboard
2. Navigate to the "AI Analysis" tab
3. Click "Run AI Analysis"
4. Wait for clustering and analysis to complete
5. Review the generated clusters and insights

### Creating Redmine Issues
**Single Issue:**
1. Click on a cluster to view details
2. Click "Assign to Redmine"
3. Fill in project, subject, and description
4. Optionally create child issues for individual failures
5. Click "Create Issue"

**Bulk Creation:**
1. Navigate to the "AI Analysis" tab
2. Click "Create All Issues"
3. Select the target Redmine project
4. Click "Create Issues"

## Project Structure

```
GMS-helper/
├── backend/
│   ├── analysis/          # AI clustering and analysis logic
│   ├── database/          # Database models and connection
│   ├── integrations/      # Redmine client
│   ├── parser/            # XML test result parsers
│   ├── routers/           # API endpoints
│   ├── static/            # Frontend files (HTML, CSS, JS)
│   ├── utils/             # Utility functions (encryption, etc.)
│   └── main.py            # FastAPI application entry point
├── docs/                  # Documentation
│   ├── DEPLOYMENT.md      # Deployment guide
│   ├── API_USAGE.md       # API usage guide
│   ├── AI_ANALYSIS.md     # AI engine details
│   ├── ARCHITECTURE.md    # System architecture
│   └── ...
├── tests/                 # Test scripts and utilities
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## 🧠 Project Context & Skills
This project utilizes specific business logic for GMS certification analysis. Agents and Developers should reference the following skills:

- **[CTS Certification Logic](docs/skills/CTS_LOGIC.md)**: Defines how submissions are grouped, how `CTSonGSI` is identified (implicit fingerprint mismatch), and how Consolidated Reports (Merge/Retry) are calculated. **Please load this skill when performing analysis or development tasks.**

## 📚 Documentation

- [Deployment Guide](docs/DEPLOYMENT.md) - Vultr + Cloudflare setup
- [API Usage](docs/API_USAGE.md) - API endpoints and examples
- [AI Analysis](docs/AI_ANALYSIS.md) - How the AI engine works
- [Architecture](docs/ARCHITECTURE.md) - System design diagrams
- [Walkthrough](docs/WALKTHROUGH.md) - Recent changes and verification

## API Endpoints

### Test Runs
- `GET /api/reports/runs` - List all test runs
- `GET /api/reports/runs/{id}` - Get run details
- `DELETE /api/reports/runs/{id}` - Delete a test run

### Analysis
- `POST /api/analysis/run/{id}` - Start AI analysis
- `GET /api/analysis/run/{id}/status` - Check analysis status
- `GET /api/analysis/run/{id}/clusters` - Get failure clusters

### Redmine Integration
- `POST /api/integrations/redmine/issue` - Create a single issue
- `POST /api/integrations/redmine/bulk-create` - Create issues for all clusters
- `POST /api/integrations/redmine/link` - Link cluster to existing issue
- `POST /api/integrations/redmine/unlink` - Unlink cluster from issue

## Database

The application uses SQLite for data storage. The database file (`gms_analysis.db`) is created automatically on first run and contains:
- Test run metadata
- Test case results
- Failure analysis and clusters
- Application settings (encrypted)

## Security

- **API Key Encryption**: All API keys (OpenAI, Redmine) are encrypted using Fernet symmetric encryption
- **Environment Variables**: Sensitive configuration can be set via environment variables
- **Secret Key**: Set `SECRET_KEY` environment variable for production deployments

## Troubleshooting

### Database Issues
If you encounter database errors, try:
```bash
python reset_db.py  # Warning: This deletes all data
```

### Analysis Not Starting
1. Verify OpenAI API key is configured in Settings
2. Check server logs for errors
3. Ensure the test run has failures to analyze

### Redmine Connection Failed
1. Verify Redmine URL is correct (include protocol: https://)
2. Check that your API key has sufficient permissions
3. Test the connection in Settings → Redmine

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

[Specify your license here]

## Support

For questions or issues, please open an issue on the repository or contact the development team.
