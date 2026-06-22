#!/bin/bash

# FstvlPress Development Setup Script
# This script sets up the complete development environment

set -e

# Print immediately so we always have output (helps when run on Windows with CRLF or early failure)
echo "FstvlPress setup starting..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MONGO_CONTAINER="mongodb"
MINIO_CONTAINER="minio"
MONGO_PORT=27017
MINIO_PORT=9000
MINIO_CONSOLE_PORT=9001
MINIO_USER="local-minio"
MINIO_PASSWORD="local-minio-password"
BUCKET_NAME="fstvlpress-assets"
DB_NAME="fstvlpress26-dev"

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if a port is in use
port_in_use() {
    lsof -i ":$1" >/dev/null 2>&1
}

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Strip carriage return if present (Windows CRLF line endings can leave \r in variable)
SCRIPT_DIR="${SCRIPT_DIR%$'\r'}"
cd "$SCRIPT_DIR"

# Parse arguments
SKIP_DEPS=false
for arg in "$@"; do
    case "$arg" in
        --skip-deps|--no-deps)
            SKIP_DEPS=true
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-deps, --no-deps   Skip prerequisite check (e.g. on unsupported platforms like Windows)"
            echo "  -h, --help               Show this help"
            exit 0
            ;;
    esac
done

print_header "FstvlPress Development Setup"

# ============================================
# STEP 1: Check Prerequisites
# ============================================
if [ "$SKIP_DEPS" = true ]; then
    print_warning "Skipping prerequisite check (--skip-deps). Ensure Node, Python, Poetry, Docker, and mongorestore are available."
    echo ""
else
print_header "Step 1: Checking Prerequisites"

MISSING_DEPS=()

# Check Node.js
if command_exists node; then
    NODE_VERSION=$(node --version | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
        print_success "Node.js v$NODE_VERSION"
    else
        print_warning "Node.js v$NODE_VERSION (recommend v18+)"
    fi
else
    print_error "Node.js not found"
    MISSING_DEPS+=("nodejs")
fi

# Check npm
if command_exists npm; then
    NPM_VERSION=$(npm --version)
    print_success "npm v$NPM_VERSION"
else
    print_error "npm not found"
    MISSING_DEPS+=("npm")
fi

# Check Python 3.12+
PYTHON_FOUND=""
# First check common commands in PATH
for py_cmd in python3.12 python3.13 python3.14 python3; do
    if command_exists "$py_cmd"; then
        PY_VERSION=$($py_cmd --version 2>/dev/null | sed 's/Python //')
        PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
        if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 12 ]; then
            PYTHON_FOUND="$py_cmd"
            print_success "Python $PY_VERSION ($(which $py_cmd))"
            break
        fi
    fi
done

# If not found, check Homebrew paths explicitly
if [ -z "$PYTHON_FOUND" ]; then
    for version in 12 13 14; do
        BREW_PYTHON="/opt/homebrew/opt/python@3.${version}/bin/python3.${version}"
        if [ -x "$BREW_PYTHON" ]; then
            PY_VERSION=$($BREW_PYTHON --version 2>/dev/null | sed 's/Python //')
            PYTHON_FOUND="$BREW_PYTHON"
            print_success "Python $PY_VERSION ($BREW_PYTHON)"
            break
        fi
    done
fi

if [ -z "$PYTHON_FOUND" ]; then
    # Show what python3 we have for context
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version | sed 's/Python //')
        print_warning "Python $PYTHON_VERSION found but require 3.12+"
    else
        print_error "Python 3 not found"
    fi
    MISSING_DEPS+=("python3.12")
fi

# Check Poetry
if command_exists poetry; then
    POETRY_VERSION=$(poetry --version | sed 's/Poetry (version //' | sed 's/)//')
    print_success "Poetry v$POETRY_VERSION"
else
    print_error "Poetry not found"
    MISSING_DEPS+=("poetry")
fi

# Check Docker
if command_exists docker; then
    if docker info >/dev/null 2>&1; then
        DOCKER_VERSION=$(docker --version | sed 's/Docker version //' | cut -d, -f1)
        print_success "Docker v$DOCKER_VERSION"
    else
        print_error "Docker is installed but not running"
        echo "       Please start Docker Desktop and try again"
        exit 1
    fi
else
    print_error "Docker not found"
    MISSING_DEPS+=("docker")
fi

# Check mongorestore (MongoDB Database Tools)
if command_exists mongorestore; then
    print_success "mongorestore (MongoDB Database Tools)"
else
    print_error "mongorestore not found (MongoDB Database Tools)"
    MISSING_DEPS+=("mongodb-database-tools")
fi

# Exit if missing dependencies
if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo ""
    print_error "Missing dependencies: ${MISSING_DEPS[*]}"
    echo ""
    echo "Installation instructions:"
    echo ""
    for dep in "${MISSING_DEPS[@]}"; do
        case $dep in
            nodejs|npm)
                echo "  Node.js & npm:"
                echo "    brew install node"
                echo "    # or download from https://nodejs.org"
                ;;
            python3.12)
                echo "  Python 3.12:"
                echo "    brew install python@3.12"
                echo "    # or download from https://python.org"
                ;;
            poetry)
                echo "  Poetry:"
                echo "    curl -sSL https://install.python-poetry.org | python3 -"
                ;;
            docker)
                echo "  Docker:"
                echo "    brew install --cask docker"
                echo "    # or download from https://docker.com"
                ;;
            mongodb-database-tools)
                echo "  MongoDB Database Tools:"
                echo "    brew tap mongodb/brew && brew install mongodb-database-tools"
                ;;
        esac
        echo ""
    done
    exit 1
fi

print_success "All prerequisites satisfied!"
fi

# ============================================
# STEP 2: Start MongoDB
# ============================================
print_header "Step 2: Setting up MongoDB"

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${MONGO_CONTAINER}$"; then
    if docker ps --format '{{.Names}}' | grep -q "^${MONGO_CONTAINER}$"; then
        print_success "MongoDB container already running"
    else
        print_info "Starting existing MongoDB container..."
        docker start "$MONGO_CONTAINER"
        print_success "MongoDB container started"
    fi
else
    print_info "Creating and starting MongoDB container..."
    docker run -d \
        --name "$MONGO_CONTAINER" \
        -p "$MONGO_PORT:27017" \
        -v mongodb-data:/data/db \
        mongo:7
    print_success "MongoDB container created and started"
fi

# Wait for MongoDB to be ready
print_info "Waiting for MongoDB to be ready..."
for i in {1..30}; do
    if docker exec "$MONGO_CONTAINER" mongosh --eval "db.runCommand('ping').ok" --quiet >/dev/null 2>&1; then
        print_success "MongoDB is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "MongoDB failed to start within 30 seconds"
        exit 1
    fi
    sleep 1
done

# ============================================
# STEP 3: Restore MongoDB Dump
# ============================================
print_header "Step 3: Restoring MongoDB Database"

DUMP_PATH="$SCRIPT_DIR/backend/dummy_data/mongo"

if [ -d "$DUMP_PATH" ]; then
    # Check if database already has data
    COLLECTION_COUNT=$(docker exec "$MONGO_CONTAINER" mongosh --quiet --eval "db.getSiblingDB('$DB_NAME').getCollectionNames().length" 2>/dev/null || echo "0")
    
    if [ "$COLLECTION_COUNT" -gt 0 ]; then
        print_warning "Database '$DB_NAME' already has $COLLECTION_COUNT collections"
        read -p "Do you want to restore anyway? This will add/update documents. (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Skipping database restore"
        else
            print_info "Restoring database from backup..."
            mongorestore --uri="mongodb://localhost:$MONGO_PORT" "$DUMP_PATH"
            print_success "Database restored"
        fi
    else
        print_info "Restoring database from backup..."
        mongorestore --uri="mongodb://localhost:$MONGO_PORT" "$DUMP_PATH"
        print_success "Database restored"
    fi
else
    print_warning "No database dump found at $DUMP_PATH"
    print_info "Continuing without database restore..."
fi

# ============================================
# STEP 4: Start MinIO
# ============================================
print_header "Step 4: Setting up MinIO (S3-compatible storage)"

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${MINIO_CONTAINER}$"; then
    if docker ps --format '{{.Names}}' | grep -q "^${MINIO_CONTAINER}$"; then
        print_success "MinIO container already running"
    else
        print_info "Starting existing MinIO container..."
        docker start "$MINIO_CONTAINER"
        print_success "MinIO container started"
    fi
else
    print_info "Creating and starting MinIO container..."
    docker run -d \
        --name "$MINIO_CONTAINER" \
        -p "$MINIO_PORT:9000" \
        -p "$MINIO_CONSOLE_PORT:9001" \
        -v minio-data:/data \
        -e "MINIO_ROOT_USER=$MINIO_USER" \
        -e "MINIO_ROOT_PASSWORD=$MINIO_PASSWORD" \
        minio/minio server /data --console-address ":9001"
    print_success "MinIO container created and started"
fi

# Wait for MinIO to be ready
print_info "Waiting for MinIO to be ready..."
for i in {1..30}; do
    if curl -s "http://localhost:$MINIO_PORT/minio/health/live" >/dev/null 2>&1; then
        print_success "MinIO is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "MinIO failed to start within 30 seconds"
        exit 1
    fi
    sleep 1
done

# Create bucket and set up access
print_info "Configuring MinIO bucket..."

# Set up mc alias
docker exec "$MINIO_CONTAINER" mc alias set local http://localhost:9000 "$MINIO_USER" "$MINIO_PASSWORD" >/dev/null 2>&1

# Create bucket if it doesn't exist
if docker exec "$MINIO_CONTAINER" mc ls local/"$BUCKET_NAME" >/dev/null 2>&1; then
    print_success "Bucket '$BUCKET_NAME' already exists"
else
    docker exec "$MINIO_CONTAINER" mc mb local/"$BUCKET_NAME" >/dev/null 2>&1
    print_success "Bucket '$BUCKET_NAME' created"
fi

# Set bucket to public (download only)
docker exec "$MINIO_CONTAINER" mc anonymous set download local/"$BUCKET_NAME" >/dev/null 2>&1
print_success "Bucket '$BUCKET_NAME' set to public (download)"

# Restore MinIO from dummy_data if available
MINIO_DUMP_PATH="$SCRIPT_DIR/backend/dummy_data/minio/$BUCKET_NAME"
if [ -d "$MINIO_DUMP_PATH" ]; then
    print_info "Restoring MinIO bucket from dummy_data..."
    # Use --entrypoint to override the default entrypoint and run shell commands
    if docker run --rm \
        --network "container:$MINIO_CONTAINER" \
        -v "$MINIO_DUMP_PATH:/source:ro" \
        --entrypoint /bin/sh \
        minio/mc \
        -c "mc alias set local http://localhost:9000 $MINIO_USER $MINIO_PASSWORD && mc mirror --overwrite /source local/$BUCKET_NAME"; then
        print_success "MinIO bucket restored from dummy_data"
    else
        print_warning "MinIO restore failed (minio/mc image may be needed: docker pull minio/mc)"
    fi
else
    print_info "No MinIO dump found at $MINIO_DUMP_PATH, skipping restore"
fi

# ============================================
# STEP 5: Install Dependencies
# ============================================
print_header "Step 5: Installing Dependencies"

# Backend
print_info "Installing backend dependencies..."
cd "$SCRIPT_DIR/backend"

# Find Python 3.12+ executable
PYTHON_CMD=""
for py_cmd in python3.12 python3.13 python3.14 python3; do
    if command_exists "$py_cmd"; then
        PY_VERSION=$($py_cmd --version 2>/dev/null | sed 's/Python //')
        PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
        if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 12 ]; then
            PYTHON_CMD="$py_cmd"
            print_info "Found Python $PY_VERSION at $(which $py_cmd)"
            break
        fi
    fi
done

# Also check Homebrew paths explicitly
if [ -z "$PYTHON_CMD" ]; then
    for version in 12 13 14; do
        BREW_PYTHON="/opt/homebrew/opt/python@3.${version}/bin/python3.${version}"
        if [ -x "$BREW_PYTHON" ]; then
            PYTHON_CMD="$BREW_PYTHON"
            PY_VERSION=$($PYTHON_CMD --version 2>/dev/null | sed 's/Python //')
            print_info "Found Python $PY_VERSION at $BREW_PYTHON"
            break
        fi
    done
fi

if [ -z "$PYTHON_CMD" ]; then
    print_error "Could not find Python 3.12+. Please install it:"
    echo "    brew install python@3.12"
    exit 1
fi

# Configure Poetry to create virtualenv in project directory
poetry config virtualenvs.in-project true --local

# Remove existing venv if it has wrong Python version
if [ -d ".venv" ]; then
    VENV_PYTHON=".venv/bin/python"
    if [ -x "$VENV_PYTHON" ]; then
        VENV_PY_VERSION=$($VENV_PYTHON --version 2>/dev/null | sed 's/Python //')
        VENV_PY_MAJOR=$(echo "$VENV_PY_VERSION" | cut -d. -f1)
        VENV_PY_MINOR=$(echo "$VENV_PY_VERSION" | cut -d. -f2)
        if [ "$VENV_PY_MAJOR" -ne 3 ] || [ "$VENV_PY_MINOR" -lt 12 ]; then
            print_warning "Existing venv uses Python $VENV_PY_VERSION, removing to recreate with 3.12+"
            rm -rf .venv
        fi
    fi
fi

# Set Poetry to use the correct Python version and install
print_info "Configuring Poetry to use Python 3.12+..."
poetry env use "$PYTHON_CMD" --quiet 2>/dev/null || poetry env use "$PYTHON_CMD"
poetry install --quiet
print_success "Backend dependencies installed (Python $(poetry run python --version | sed 's/Python //'))"

# Frontend
print_info "Installing frontend dependencies..."
cd "$SCRIPT_DIR/frontend"

# Find Node 20+ executable
NODE_CMD="node"
NODE_VERSION=$(node -v 2>/dev/null | cut -d'v' -f2 | cut -d'.' -f1)

if [ -z "$NODE_VERSION" ] || [ "$NODE_VERSION" -lt 20 ]; then
    # Try Homebrew Node installations
    for version in 20 22 24; do
        BREW_NODE="/opt/homebrew/opt/node@${version}/bin"
        if [ -d "$BREW_NODE" ]; then
            export PATH="$BREW_NODE:$PATH"
            NODE_VERSION=$(node -v 2>/dev/null | cut -d'v' -f2 | cut -d'.' -f1)
            print_info "Using Homebrew Node $(node -v)"
            break
        fi
    done
fi

if [ -z "$NODE_VERSION" ] || [ "$NODE_VERSION" -lt 20 ]; then
    print_warning "Node.js $(node -v 2>/dev/null || echo 'not found'). Vite requires Node 20+."
    print_info "Consider: brew install node@20"
fi

npm install --silent
print_success "Frontend dependencies installed (Node $(node -v))"

cd "$SCRIPT_DIR"

# ============================================
# STEP 6: Start Services
# ============================================
print_header "Step 6: Starting Services"

echo ""
echo "Starting backend and frontend in separate terminal sessions..."
echo ""
echo -e "${YELLOW}NOTE: This will open new terminal windows/tabs${NC}"
echo ""

BACKEND_ENV="MONGO_URI=mongodb://localhost:$MONGO_PORT MONGO_DB=$DB_NAME STORAGE_BACKEND=s3 S3_ENDPOINT_URL=http://localhost:$MINIO_PORT S3_ACCESS_KEY_ID=$MINIO_USER S3_SECRET_ACCESS_KEY=$MINIO_PASSWORD S3_BUCKET=$BUCKET_NAME S3_PUBLIC_BASE_URL=http://localhost:$MINIO_PORT/$BUCKET_NAME"

# Determine the OS and open terminals accordingly
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - use osascript to open Terminal windows
    
    # Start Backend on port 8080
    osascript -e "tell application \"Terminal\" to do script \"cd '$SCRIPT_DIR/backend' && echo 'Starting Backend on port 8080...' && $BACKEND_ENV poetry run uvicorn app.main:app --reload --port 8080\""
    print_success "Backend starting in new Terminal window"
    
    # Small delay to avoid race conditions
    sleep 1
    
    # Start Frontend (with API pointing to port 8080)
    osascript -e "tell application \"Terminal\" to do script \"cd '$SCRIPT_DIR/frontend' && echo 'Starting Frontend...' && VITE_API_BASE=http://localhost:8080/api/v1 npm run dev\""
    print_success "Frontend starting in new Terminal window"
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux - try various terminal emulators
    if command_exists gnome-terminal; then
        gnome-terminal -- bash -c "cd '$SCRIPT_DIR/backend' && $BACKEND_ENV poetry run uvicorn app.main:app --reload --port 8080; exec bash"
        gnome-terminal -- bash -c "cd '$SCRIPT_DIR/frontend' && VITE_API_BASE=http://localhost:8080/api/v1 npm run dev; exec bash"
    elif command_exists xterm; then
        xterm -e "cd '$SCRIPT_DIR/backend' && $BACKEND_ENV poetry run uvicorn app.main:app --reload --port 8080" &
        xterm -e "cd '$SCRIPT_DIR/frontend' && VITE_API_BASE=http://localhost:8080/api/v1 npm run dev" &
    else
        print_warning "Could not detect terminal emulator"
        echo "Please start the services manually:"
        echo "  Backend: cd backend && $BACKEND_ENV poetry run uvicorn app.main:app --reload --port 8080"
        echo "  Frontend: cd frontend && VITE_API_BASE=http://localhost:8080/api/v1 npm run dev"
    fi
else
    print_warning "Unsupported OS for automatic terminal opening"
    echo "Please start the services manually:"
    echo "  Backend: cd backend && $BACKEND_ENV poetry run uvicorn app.main:app --reload --port 8080"
    echo "  Frontend: cd frontend && VITE_API_BASE=http://localhost:8080/api/v1 npm run dev"
fi

# ============================================
# Summary
# ============================================
print_header "Setup Complete!"

echo -e "${GREEN}Services are starting...${NC}"
echo ""
echo "Access points:"
echo "  Frontend:      http://localhost:5173"
echo "  Backend API:   http://localhost:8080"
echo "  API Docs:      http://localhost:8080/docs"
echo "  MinIO Console: http://localhost:9001 ($MINIO_USER/$MINIO_PASSWORD)"
echo ""
echo "To stop services:"
echo "  - Close the terminal windows running frontend/backend"
echo "  - Run: docker stop mongodb minio"
echo ""
echo -e "${BLUE}Happy coding! 🎉${NC}"
