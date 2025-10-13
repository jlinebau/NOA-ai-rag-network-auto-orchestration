# NOA is an AI-driven app using RAG (Retrieval-Augmented Generation) for network orchestration and automation

This project integrates a Retrieval-Augmented Generation (RAG) workflow using **SQLite**, **FastAPI**, and **Ollama (Mistral)** to generate intelligent network configurations based on real CLI examples.
NOA is a FastAPI-based application designed to assist network engineers in generating, reviewing, and pushing CLI configurations to network devices. It integrates with a CLI example database to augment the use an LLM (via Ollama) to generate configurations based on device parameters and features.

## Features

- Webhook integration for automated configuration requests
- CLI config generation using LLM
- Review and approval UI with HTTP Basic authentication
- Push configurations to devices via SSH
- SQLite-based staging queue and CLI library
- Fuzzy matching for vendor/model/feature lookups
- Logging of all major operations

---

## 📦 Components

### 1. `cli_library.db`
SQLite database storing CLI examples extracted from vendor documentation.

### 2. `cli_library.py`
Utility functions to:
- Initialize the database
- Add/query CLI entries
- Export CLI blocks

### 3. `parse_cli_file.py`
Parses CLI blocks from `cisco_cat_9200.txt` and inserts them into the database using `###` markers.

### 4. `rag_api.py`
FastAPI app that:
- Accepts config generation requests
- Queries CLI examples from SQLite
- Builds prompt
- Sends prompt to Mistral via Ollama
- Returns generated config

