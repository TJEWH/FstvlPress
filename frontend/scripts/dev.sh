#!/bin/bash
# Development server startup script
# This script finds and uses Node.js 20+ across different OS and installers

set -e

# Required Node major version
REQUIRED_NODE_MAJOR=22

# Function to get Node major version from a path
get_node_major() {
    local node_path="$1"
    if [ -x "$node_path" ]; then
        "$node_path" -v 2>/dev/null | cut -d'v' -f2 | cut -d'.' -f1
    fi
}

# Function to check if current node meets requirements
check_current_node() {
    local version=$(node -v 2>/dev/null | cut -d'v' -f2 | cut -d'.' -f1)
    [ -n "$version" ] && [ "$version" -ge "$REQUIRED_NODE_MAJOR" ]
}

echo "Finding Node.js $REQUIRED_NODE_MAJOR+..."

# If current node already meets requirements, use it
if check_current_node; then
    echo "Using Node $(node -v) from PATH"
    exec npm run dev
fi

NODE_FOUND=false

# Option 1: nvm (Node Version Manager)
if [ -f "$HOME/.nvm/nvm.sh" ]; then
    echo "Checking nvm..."
    source "$HOME/.nvm/nvm.sh"
    # Try Node versions in order of preference
    for version in 22 20 21 23 24; do
        if nvm list "$version" &>/dev/null; then
            nvm use "$version" --silent
            if check_current_node; then
                echo "Using Node $(node -v) via nvm"
                NODE_FOUND=true
                break
            fi
        fi
    done
fi

# Option 2: fnm (Fast Node Manager)
if [ "$NODE_FOUND" = false ] && command -v fnm &>/dev/null; then
    echo "Checking fnm..."
    eval "$(fnm env --shell bash 2>/dev/null)" || true
    for version in 22 20 21 23 24; do
        if fnm use "$version" &>/dev/null; then
            if check_current_node; then
                echo "Using Node $(node -v) via fnm"
                NODE_FOUND=true
                break
            fi
        fi
    done
fi

# Option 3: volta
if [ "$NODE_FOUND" = false ] && [ -d "$HOME/.volta" ]; then
    echo "Checking volta..."
    export VOLTA_HOME="$HOME/.volta"
    export PATH="$VOLTA_HOME/bin:$PATH"
    if check_current_node; then
        echo "Using Node $(node -v) via volta"
        NODE_FOUND=true
    fi
fi

# Option 4: Homebrew (macOS)
if [ "$NODE_FOUND" = false ]; then
    # Detect Homebrew prefix (Apple Silicon vs Intel)
    if [ -d "/opt/homebrew" ]; then
        BREW_PREFIX="/opt/homebrew"
    elif [ -d "/usr/local/Homebrew" ]; then
        BREW_PREFIX="/usr/local"
    fi
    
    if [ -n "$BREW_PREFIX" ]; then
        echo "Checking Homebrew..."
        # Try versioned node installations first, then default
        for version in 20 22 24 ""; do
            if [ -n "$version" ]; then
                NODE_BIN="$BREW_PREFIX/opt/node@${version}/bin"
            else
                NODE_BIN="$BREW_PREFIX/opt/node/bin"
            fi
            
            if [ -d "$NODE_BIN" ]; then
                NODE_MAJOR=$(get_node_major "$NODE_BIN/node")
                if [ -n "$NODE_MAJOR" ] && [ "$NODE_MAJOR" -ge "$REQUIRED_NODE_MAJOR" ]; then
                    export PATH="$NODE_BIN:$PATH"
                    echo "Using Node $(node -v) from Homebrew ($NODE_BIN)"
                    NODE_FOUND=true
                    break
                fi
            fi
        done
    fi
fi

# Option 5: Common Linux paths
if [ "$NODE_FOUND" = false ]; then
    echo "Checking common installation paths..."
    for node_path in /usr/local/bin/node /usr/bin/node; do
        NODE_MAJOR=$(get_node_major "$node_path")
        if [ -n "$NODE_MAJOR" ] && [ "$NODE_MAJOR" -ge "$REQUIRED_NODE_MAJOR" ]; then
            export PATH="$(dirname "$node_path"):$PATH"
            echo "Using Node $(node -v) from $node_path"
            NODE_FOUND=true
            break
        fi
    done
fi

# Final check
if [ "$NODE_FOUND" = false ]; then
    CURRENT_VERSION=$(node -v 2>/dev/null || echo "not found")
    echo ""
    echo "ERROR: Node.js $REQUIRED_NODE_MAJOR+ not found!"
    echo "Current Node: $CURRENT_VERSION"
    echo ""
    echo "Please install Node.js $REQUIRED_NODE_MAJOR+ using one of:"
    echo "  - nvm: nvm install 22 && nvm use 22"
    echo "  - Homebrew (macOS): brew install node@20"
    echo "  - Download from: https://nodejs.org"
    exit 1
fi

# Run the dev server
exec npm run dev
