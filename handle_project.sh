#!/bin/bash
set -e

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"
STREAMLIT_BIN="$VENV_DIR/bin/streamlit"
REQUIREMENTS="$PROJECT_ROOT/requirements.txt"

# Force offline mode for HuggingFace (ensure models are loaded from cache)
export HF_HUB_OFFLINE=1

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err() { echo -e "${RED}[ERROR]${NC} $1"; }

check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        log_warn "Virtual environment not found. Please run './handle_project.sh install' first."
        exit 1
    fi
}

cmd_install() {
    log_info "Setting up virtual environment..."
    if [ ! -d "$VENV_DIR" ]; then
        # Try to find python 3.12 or 3.13 or 3.11, avoid 3.14
        if command -v python3.12 &> /dev/null; then
            PYTHON_CMD=python3.12
        elif command -v python3.13 &> /dev/null; then
            PYTHON_CMD=python3.13
        elif command -v python3.11 &> /dev/null; then
            PYTHON_CMD=python3.11
        elif command -v python3.10 &> /dev/null; then
            PYTHON_CMD=python3.10
        else
            # Fallback to default python3
            PYTHON_CMD=python3
        fi
        
        log_info "Using python executable: $PYTHON_CMD"
        "$PYTHON_CMD" -m venv "$VENV_DIR"
        log_info "Created venv at $VENV_DIR"
    else
        log_info "Venv already exists."
    fi
    
    log_info "Installing dependencies..."
    # Ensure we use the pip inside the venv
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install --upgrade wheel setuptools
    "$VENV_DIR/bin/pip" install -r "$REQUIREMENTS"
    
    log_info "Setup complete!"
}

cmd_start() {
    check_venv
    log_info "Starting CLI Agent..."
    "$PYTHON_BIN" main.py
}

cmd_query() {
    check_venv
    local user_query=""
    shift  # rimuovi il comando 'query' da $@
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --user-query)
                shift
                user_query="$1"
                ;;
            *)
                # Se non c'è --user-query, tratta tutto come query
                user_query="$*"
                break
                ;;
        esac
        shift
    done

    if [ -z "$user_query" ]; then
        log_err "Specificare la query: ./handle_project.sh query --user-query \"la tua domanda\""
        exit 1
    fi

    log_info "Running query: $user_query"
    "$PYTHON_BIN" main.py "$user_query"
}

cmd_ingest() {
    check_venv
    log_info "Starting Document Ingestion..."
    "$PYTHON_BIN" -m ingest.ingest
}

cmd_web() {
    check_venv
    log_info "Starting Web Interface (Streamlit)..."
    if [ ! -f "$STREAMLIT_BIN" ]; then
        log_err "Streamlit not found. Run './handle_project.sh install' first."
        exit 1
    fi
    "$STREAMLIT_BIN" run app.py
}

cmd_clean() {
    log_info "Cleaning temporary files..."
    find . -type d -name "__pycache__" -exec rm -rf {} +
    rm -rf .pytest_cache
    rm -rf build dist *.egg-info
    log_info "Clean complete."
}

show_help() {
    echo "Usage: ./handle_project.sh [command]"
    echo ""
    echo "Commands:"
    echo "  install                          Create venv and install requirements"
    echo "  start                            Run the CLI agent (interactive REPL)"
    echo "  query --user-query \"text\"        Run a single query and print result"
    echo "  web                              Run the Web Interface (Streamlit)"
    echo "  ingest                           Run document ingestion"
    echo "  clean                            Remove temporary files"
    echo "  help                             Show this help message"
}

# Main dispatcher
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

case "$1" in
    install) cmd_install ;;
    start)   cmd_start ;;
    query)   cmd_query "$@" ;;
    web)     cmd_web ;;
    ingest)  cmd_ingest ;;
    clean)   cmd_clean ;;
    help)    show_help ;;
    *)       show_help ;;
esac
