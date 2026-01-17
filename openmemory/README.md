# OpenMemory

OpenMemory is your personal memory layer for LLMs - private, portable, and open-source. Your memories live locally, giving you complete control over your data. Build AI applications with personalized memories while keeping your data secure.

![OpenMemory](https://github.com/user-attachments/assets/3c701757-ad82-4afa-bfbe-e049c2b4320b)

## Easy Setup

### Prerequisites
- Docker
- OpenAI API Key

You can quickly run OpenMemory by running the following command:

```bash
curl -sL https://raw.githubusercontent.com/mem0ai/mem0/main/openmemory/run.sh | bash
```

You should set the `OPENAI_API_KEY` as a global environment variable:

```bash
export OPENAI_API_KEY=your_api_key
```

You can also set the `OPENAI_API_KEY` as a parameter to the script:

```bash
curl -sL https://raw.githubusercontent.com/mem0ai/mem0/main/openmemory/run.sh | OPENAI_API_KEY=your_api_key bash
```

## Prerequisites

- Docker and Docker Compose
- Python 3.9+ (for backend development)
- Node.js (for frontend development)
- OpenAI API Key (required for LLM interactions, run `cp api/.env.example api/.env` then change **OPENAI_API_KEY** to yours)

## Quickstart

### 1. Set Up Environment Variables

Before running the project, you need to configure environment variables for both the API and the UI.

You can do this in one of the following ways:

- **Manually**:  
  Create a `.env` file in each of the following directories:
  - `/api/.env`
  - `/ui/.env`

- **Using `.env.example` files**:  
  Copy and rename the example files:

  ```bash
  cp api/.env.example api/.env
  cp ui/.env.example ui/.env
  ```

 - **Using Makefile** (if supported):  
    Run:
  
   ```bash
   make env
   ```
- #### Example `/api/.env`

```env
OPENAI_API_KEY=sk-xxx
USER=<user-id> # The User Id you want to associate the memories with
```

- #### LLM Configuration (optional)

By default, OpenMemory uses OpenAI (`gpt-4o-mini`) for the LLM and embedder. You can configure a different provider using these environment variables in `/api/.env`:

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | LLM provider (`openai`, `ollama`, `anthropic`, `groq`, `together`, `deepseek`, etc.) | `openai` |
| `LLM_MODEL` | Model name for the LLM provider | `gpt-4o-mini` (OpenAI) / `llama3.1:latest` (Ollama) |
| `LLM_API_KEY` | API key for the LLM provider | `OPENAI_API_KEY` env var |
| `LLM_BASE_URL` | Custom base URL for the LLM API | Provider default |
| `OLLAMA_BASE_URL` | Ollama-specific base URL (takes precedence over `LLM_BASE_URL` for Ollama) | `http://localhost:11434` |
| `EMBEDDER_PROVIDER` | Embedder provider (defaults to `ollama` when LLM is Ollama, otherwise `openai`) | `openai` |
| `EMBEDDER_MODEL` | Model name for the embedder | `text-embedding-3-small` (OpenAI) / `nomic-embed-text` (Ollama) |
| `EMBEDDER_API_KEY` | API key for the embedder provider | `OPENAI_API_KEY` env var |
| `EMBEDDER_BASE_URL` | Custom base URL for the embedder API | Provider default |

**Example: Using Ollama (fully local)**
```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:latest
EMBEDDER_PROVIDER=ollama
EMBEDDER_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

**Example: Using Anthropic**
```env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
LLM_API_KEY=sk-ant-xxx
```
- #### Example `/ui/.env`

```env
NEXT_PUBLIC_API_URL=http://localhost:8765
NEXT_PUBLIC_USER_ID=<user-id> # Same as the user id for environment variable in api
```

### 2. Build and Run the Project
You can run the project using the following two commands:
```bash
make build # builds the mcp server and ui
make up  # runs openmemory mcp server and ui
```

After running these commands, you will have:
- OpenMemory MCP server running at: http://localhost:8765 (API documentation available at http://localhost:8765/docs)
- OpenMemory UI running at: http://localhost:3000

#### UI not working on `localhost:3000`?

If the UI does not start properly on [http://localhost:3000](http://localhost:3000), try running it manually:

```bash
cd ui
pnpm install
pnpm dev
```

### MCP Client Setup

Use the following one step command to configure OpenMemory Local MCP to a client. The general command format is as follows:

```bash
npx @openmemory/install local http://localhost:8765/mcp/<client-name>/sse/<user-id> --client <client-name>
```

Replace `<client-name>` with the desired client name and `<user-id>` with the value specified in your environment variables.

## Graph Memory (Neo4j)

Graph memory is optional and can be enabled via environment variables on the API service.

Enable it:
```bash
export NEO4J_ENABLED=true
export NEO4J_URL=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=password
export NEO4J_DATABASE=mem0
```

Start a local Neo4j instance:
```bash
docker run --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password neo4j:latest
```

Example MCP tool usage:
```json
{"tool": "graph_add_entity", "args": {"name": "USB_CDC_Function", "entity_type": "function", "attributes": "{\"confidence\": 0.9, \"status\": \"verified\"}"}}
{"tool": "graph_add_relation", "args": {"from_entity": "USB_CDC_Function", "to_entity": "addr_0x8001234", "relation_type": "located_at", "attributes": "{\"source\": \"ghidra\"}"}}
{"tool": "graph_query", "args": {"query": "USB_CDC_Function", "limit": 10}}
```


## Project Structure

- `api/` - Backend APIs + MCP server
- `ui/` - Frontend React application

## Contributing

We are a team of developers passionate about the future of AI and open-source software. With years of experience in both fields, we believe in the power of community-driven development and are excited to build tools that make AI more accessible and personalized.

We welcome all forms of contributions:
- Bug reports and feature requests
- Documentation improvements
- Code contributions
- Testing and feedback
- Community support

How to contribute:

1. Fork the repository
2. Create your feature branch (`git checkout -b openmemory/feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin openmemory/feature/amazing-feature`)
5. Open a Pull Request

Join us in building the future of AI memory management! Your contributions help make OpenMemory better for everyone.
