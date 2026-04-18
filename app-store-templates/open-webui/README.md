Open WebUI is a feature-rich, self-hosted web interface for interacting with large language models (LLMs). It works seamlessly with Ollama for local model inference and supports any OpenAI-compatible API.

## Features

- 🤖 Chat with local LLMs via Ollama (Llama, Mistral, Gemma, Phi, and more)
- 🔌 OpenAI API compatibility (connect to external providers)
- 💬 Persistent chat history per user
- 👥 Multi-user support with role-based access control
- 🧠 System prompt and persona configuration
- 📎 File and image uploads (vision-capable models)
- 🎨 Fully responsive, dark/light theme
- 📦 Model management – pull and delete models directly from the UI
- 🔑 API key management for external providers

## Default Access

- **URL:** `http://<your-server>:3000`
- The first registered user automatically becomes the admin.

## Data & Persistence

| Path | Description |
|---|---|
| `/opt/upservx/data/open-webui` | Chat history, users, settings |
| `/opt/upservx/data/ollama` | Downloaded LLM model files |

## Pulling Models

After starting, open the UI and go to **Settings → Models** to pull models, or use the Ollama CLI:

```bash
docker exec -it ollama ollama pull llama3
docker exec -it ollama ollama pull mistral
docker exec -it ollama ollama pull gemma3
```

## GPU Support (NVIDIA)

Uncomment the `deploy` section in `docker-compose.yml` and ensure the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) is installed on the host.

## Connecting to an External OpenAI-Compatible API

In the UI go to **Settings → Connections** and add your API base URL and key. Remove or disable the Ollama service in `docker-compose.yml` if you only use external APIs.

## Official Documentation

https://docs.openwebui.com/
