Ollama lets you run large language models (LLMs) locally on your own hardware. It provides a simple REST API and CLI to download, manage, and query models like Llama 3, Mistral, Gemma, Phi, and many more.

## Features

- 🦙 Run LLMs fully locally – no cloud required
- 📦 One-command model downloads (`ollama pull`)
- 🔌 OpenAI-compatible REST API
- ⚡ Optimized inference with CPU and GPU support
- 🧠 Support for dozens of models (Llama 3, Mistral, Gemma, Phi, Qwen, DeepSeek, and more)
- 🔧 Custom model creation via Modelfiles
- 🌐 Works as a backend for Open WebUI and other frontends

## Default Access

- **API URL:** `http://<your-server>:11434`

## Pulling Models

Use the Docker CLI to pull models after the container is running:

```bash
docker exec -it ollama ollama pull llama3
docker exec -it ollama ollama pull mistral
docker exec -it ollama ollama pull gemma3
docker exec -it ollama ollama pull phi3
```

List all available models:

```bash
docker exec -it ollama ollama list
```

## API Usage

```bash
curl http://<your-server>:11434/api/generate -d '{
  "model": "llama3",
  "prompt": "Why is the sky blue?"
}'
```

## Data & Persistence

| Path | Description |
|---|---|
| `/opt/upservx/data/ollama` | Downloaded model files |

## GPU Support (NVIDIA)

Uncomment the `deploy` section in `docker-compose.yml` and ensure the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) is installed on the host.

## Official Documentation

https://ollama.com/
