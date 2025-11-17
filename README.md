# Personal Deepseek Agent

A comprehensive LangChain-based personal assistant system with multi-LLM support, dynamic memory management, Google Search integration, and GitHub operations. Designed to work seamlessly with Feishu webhooks via GitHub Actions.

## Features

- **Multi-LLM Support**: Works with OpenAI, Deepseek, and Google Gemini
- **Dynamic Memory Management**: Clones and manages a private memory repository, intelligently loads relevant memories, and creates/updates memories based on interactions
- **Google Search Integration**: Automatically determines when to search the web for current information
- **GitHub Operations**: Perform GitHub repository operations with memory of different repositories
- **LangChain-Based**: Built on LangChain for robust agent orchestration and tool integration
- **Feishu Integration**: Sends responses via Feishu webhooks

## Architecture

```
assistant/
├── core/
│   ├── config.py              # Configuration management
│   ├── llm_provider.py        # Multi-LLM provider abstraction
│   └── orchestrator.py        # Main orchestration with LangChain agents
├── memory/
│   ├── repository_manager.py  # Git-based memory repository management
│   ├── memory_store.py        # Vector store for semantic memory search
│   └── memory_analyzer.py     # LLM-powered memory analysis
└── tools/
    ├── search_tool.py         # Google Search with intelligent decision making
    └── github_tool.py         # GitHub API operations
```

## Installation

### Using uv (Recommended)

This project uses [uv](https://github.com/astral-sh/uv) for fast package management.

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (cloud-based embeddings, no CUDA required)
uv pip install -e .

# Or install with dev dependencies
uv pip install -e ".[dev]"

# Optional: Install local embeddings support (requires CUDA/GPU)
uv pip install -e ".[local-embeddings]"
```

### Using pip

```bash
pip install -r requirements.txt

# Optional: Install local embeddings (sentence-transformers)
# Only needed if you want local embeddings instead of cloud-based
pip install sentence-transformers
```

## Configuration

The system uses environment variables for configuration. Set the following:

### Required Configuration

```bash
# LLM Provider (choose one)
LLM_PROVIDER=deepseek  # or "openai" or "gemini"
DEEPSEEK_API_KEY=your-deepseek-api-key
# OR
OPENAI_API_KEY=your-openai-api-key
# OR
GEMINI_API_KEY=your-gemini-api-key

# Feishu Webhook
FEISHU_WEBHOOK_URL=https://your-feishu-webhook-url
```

### Optional Configuration

```bash
# Memory Repository (for persistent memory)
MEMORY_REPO_URL=https://github.com/your-username/your-memory-repo.git
MEMORY_REPO_TOKEN=your-github-token  # Required for private repos
MEMORY_REPO_PATH=./memory_repo  # Default: ./memory_repo

# Embedding Configuration (for memory search)
# Note: Cloud-based embeddings are used by default (no CUDA required for GitHub Actions)
EMBEDDING_PROVIDER=auto  # auto, openai, gemini, or simple
# If using OpenAI for embeddings (recommended for best results)
OPENAI_API_KEY=your-openai-api-key  # Can be different from LLM provider
OPENAI_EMBEDDING_MODEL=text-embedding-3-small  # Default embedding model
# If using Gemini for embeddings
GEMINI_API_KEY=your-gemini-api-key  # Can be different from LLM provider
# If using simple keyword-based search (fallback, no API needed)
EMBEDDING_PROVIDER=simple

# Google Search (for web search functionality)
GOOGLE_API_KEY=your-google-api-key
GOOGLE_CSE_ID=your-custom-search-engine-id

# GitHub Operations
GITHUB_TOKEN=your-github-token  # Or use secrets.GITHUB_TOKEN in GitHub Actions

# Model Selection (optional, defaults provided)
DEEPSEEK_MODEL=deepseek-chat
OPENAI_MODEL=gpt-4o-mini
GEMINI_MODEL=gemini-pro

# Assistant Settings
TEMPERATURE=0.7  # Default: 0.7
MAX_TOKENS=2000  # Default: 2000
```

## Usage

### Local Development

```bash
python main.py \
    --question "What is the weather today?" \
    --user "test_user" \
    --time "2024-01-01 12:00:00"
```

### GitHub Actions

The system is designed to work with GitHub Actions workflows. See `.github/workflows/feishu_assistant_processor.yaml` for the workflow configuration.

1. Add the required secrets to your GitHub repository:
   - `FEISHU_WEBHOOK_URL`
   - `LLM_PROVIDER`
   - At least one LLM API key (`DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`)
   - Optional: `MEMORY_REPO_URL`, `MEMORY_REPO_TOKEN`, `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`, etc.

2. Trigger the workflow manually with:
   - Question: Your question
   - User: Feishu user identifier
   - Time: Timestamp of the question

## Embeddings

The system uses **cloud-based embeddings by default** for GitHub Actions compatibility (no CUDA required).

### Embedding Providers

1. **OpenAI Embeddings** (Recommended)
   - High quality, fast, reliable
   - Requires `OPENAI_API_KEY`
   - Default model: `text-embedding-3-small`
   - Can be used even if your LLM provider is different

2. **Google Gemini Embeddings**
   - Good quality, alternative to OpenAI
   - Requires `GEMINI_API_KEY`
   - Model: `models/embedding-001`

3. **Simple Keyword Embeddings** (Fallback)
   - Lightweight, no API required
   - No ML, no CUDA, works everywhere
   - Lower quality but functional
   - Automatically used if no cloud API keys are set

### Configuration

Set `EMBEDDING_PROVIDER` to control which provider to use:
- `auto` (default): Automatically selects best available provider
- `openai`: Force OpenAI embeddings
- `gemini`: Force Gemini embeddings
- `simple`: Use simple keyword-based search

**Note**: For best results in GitHub Actions, set `OPENAI_API_KEY` even if you're using Deepseek for the LLM.

## Memory Repository

The system supports a private Git repository for persistent memory storage:

1. **Structure**: The memory repository can contain:
   - JSON files with structured memories
   - Markdown/text files with notes
   - Any format in the `memories/` directory

2. **Operations**:
   - **Load**: Automatically clones/updates the repository and loads memories
   - **Analyze**: Uses LLM to determine which memories are relevant to each question
   - **Create**: Automatically creates new memories from important interactions
   - **Delete**: Identifies and removes outdated memories

3. **Example Memory Format**:
```json
{
  "content": "User prefers Python over Java for backend development",
  "source": "interaction_20240101_120000",
  "timestamp": "2024-01-01T12:00:00",
  "user": "test_user",
  "related_question": "What programming language should I use?"
}
```

## Testing

Run tests using pytest:

```bash
# Install test dependencies
uv pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=assistant --cov=main --cov-report=html

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v
```

## Development

### Code Quality

This project uses several tools for code quality:

- **Black**: Code formatting
- **Ruff**: Fast linting
- **MyPy**: Type checking
- **Pytest**: Testing

```bash
# Format code
black assistant/ main.py tests/

# Lint code
ruff check assistant/ main.py tests/

# Type check
mypy assistant/ main.py
```

### Project Structure

```
.
├── assistant/              # Main package
│   ├── core/              # Core components
│   ├── memory/             # Memory management
│   └── tools/              # Tools (search, GitHub)
├── tests/                  # Test suite
├── main.py                 # Entry point
├── pyproject.toml          # Project configuration (uv)
├── requirements.txt        # Dependencies (pip)
└── README.md              # This file
```

## How It Works

1. **Question Reception**: Receives question from Feishu via GitHub Actions
2. **Memory Loading**: Clones/updates memory repository and loads relevant memories
3. **Context Analysis**: Uses LLM to analyze question and determine:
   - Which memories are relevant
   - Whether web search is needed
   - What new memories should be created
   - Which old memories should be deleted
4. **Tool Execution**: Uses appropriate tools (search, GitHub) if needed
5. **Response Generation**: Generates response using LLM with context
6. **Memory Update**: Creates/updates memories and commits to repository
7. **Response Delivery**: Sends formatted response to Feishu

## LLM Provider Support

### Deepseek (Default)
- Uses OpenAI-compatible API
- Base URL: `https://api.deepseek.com/v1`
- Default model: `deepseek-chat`

### OpenAI
- Standard OpenAI API
- Default model: `gpt-4o-mini`

### Google Gemini
- Google Generative AI API
- Default model: `gemini-pro`

## Tools

### Google Search Tool
- Automatically determines when search is needed
- Uses LLM to decide if question requires current information
- Formats search results for context

### GitHub Tool
- List repositories
- Get repository information
- Create issues
- List issues
- Get file content
- Remembers repository information in memory

## Troubleshooting

### Common Issues

1. **LLM API Key Not Found**
   - Ensure you've set the correct API key for your chosen provider
   - Check that `LLM_PROVIDER` matches your API key

2. **Memory Repository Access Denied**
   - Ensure `MEMORY_REPO_TOKEN` is set for private repositories
   - Check that the token has repository access permissions

3. **Tool Initialization Failed**
   - Some tools are optional (Google Search, GitHub)
   - System will work in LLM-only mode if tools fail to initialize

4. **Agent Creation Failed**
   - Some LLM providers may not support tool calling
   - System automatically falls back to direct LLM calls

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

MIT License

## Author

Owen - PhD student in Robotics and Autonomous Driving

## Acknowledgments

- Built with [LangChain](https://www.langchain.com/)
- Uses [uv](https://github.com/astral-sh/uv) for package management
- Integrates with Feishu, GitHub, and various LLM providers

