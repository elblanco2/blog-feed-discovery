# Blog Feed Discovery

A Python tool to discover and validate RSS/Atom feeds from blog URLs and titles.

## Features

- Discovers RSS and Atom feeds from blog URLs
- Supports multiple feed discovery methods:
  - Common URL patterns
  - HTML parsing for feed links
  - CMS-specific patterns
- Validates discovered feeds
- Handles redirects and common edge cases
- Comprehensive error handling and logging
- Asynchronous processing for better performance

## macOS Installation Guide

### Prerequisites

1. **Install Homebrew** (if not already installed):
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

2. **Install Python 3** (if not already installed):
```bash
brew install python
```

3. **Install Git** (if not already installed):
```bash
brew install git
```

### Installation Steps

1. **Clone the repository:**
```bash
git clone https://github.com/elblanco2/blog-feed-discovery.git
cd blog-feed-discovery
```

2. **Create and activate a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install required packages:**
```bash
pip install -r requirements.txt
```

### Verification

To verify the installation:
```bash
python3
>>> from feed_finder import FeedFinder
>>> finder = FeedFinder()
>>> exit()
```

If no errors appear, the installation was successful.

### Troubleshooting

If you encounter any issues:

1. **SSL Certificate errors:**
```bash
pip install --upgrade certifi
```

2. **Permission errors:**
```bash
sudo chown -R $(whoami) $(brew --prefix)/*
```

3. **Python version conflicts:**
```bash
brew unlink python && brew link python
```

4. **Package installation failures:**
Try updating pip:
```bash
pip install --upgrade pip
```

For other issues, please check the [Issues](https://github.com/elblanco2/blog-feed-discovery/issues) page.

## Usage

```python
from feed_finder import FeedFinder

# Initialize the finder
finder = FeedFinder()

# Find feeds for a single blog
result = finder.find_feed('example.com')
print(result)

# Process multiple blogs from a file
finder.process_file('blogs.csv', 'output.csv')
```

## Input Format

The tool accepts input in CSV format with the following columns:
- `blog_title` (optional)
- `blog_url` (required)

## Output Format

Results are saved in CSV format with the following columns:
- Blog URL
- Feed URL
- Feed type (RSS/Atom)
- Status
- Error message (if any)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.