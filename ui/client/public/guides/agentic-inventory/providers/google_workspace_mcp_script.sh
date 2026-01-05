#!/bin/bash

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_error() {
    echo -e "${RED}❌ ERROR: $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

print_step() {
    echo -e "${BLUE}▶ $1${NC}"
}

# Function to display usage
usage() {
    cat << EOF
Usage: $0 <JSON_FILE> [OPTIONS]

Required arguments:
  JSON_FILE           Path to JSON file containing Google OAuth credentials
                     Expected structure: {"web": {"client_id": "...", "client_secret": "...", "project_id": "..."}}
  --user_email        User's Google email address

Optional arguments:
  --enable_services   Enable Google Cloud APIs (requires project_id in JSON)
  --services          Comma-separated list of services to enable
                      Default: gmail,calendar,drive,docs,sheets,slides,tasks,contacts
  --skip_gcloud       Skip gcloud CLI validation and service enablement

Available services:
  - gmail             Gmail API
  - calendar          Google Calendar API
  - drive             Google Drive API
  - docs              Google Docs API
  - sheets            Google Sheets API
  - slides            Google Slides API
  - tasks             Google Tasks API
  - contacts          People API (for contacts)
  - admin             Admin SDK API
  - meet              Google Meet API

Example JSON file structure:
  {
    "web": {
      "client_id": "123456.apps.googleusercontent.com",
      "client_secret": "GOCSPX-abcdef123456",
      "project_id": "my-project-123"
    }
  }

Example usage:
  $0 credentials.json --user_email "user@example.com" --enable_services
  
  Note: --user_email is required. All other flags are optional.

EOF
    exit 1
}

# Function to extract JSON value using available tools
extract_json_value() {
    local json_file="$1"
    local json_path="$2"
    local result=""
    
    # Try jq first (most common and reliable)
    if command -v jq &> /dev/null; then
        result=$(jq -r "$json_path" "$json_file" 2>/dev/null)
        if [ $? -eq 0 ] && [ "$result" != "null" ] && [ -n "$result" ]; then
            echo "$result"
            return 0
        fi
    fi
    
    # Fall back to Python 3 (usually available)
    if command -v python3 &> /dev/null; then
        if [ "$json_path" = ".web.client_id" ]; then
            result=$(python3 -c "import json; data = json.load(open('$json_file')); print(data.get('web', {}).get('client_id', ''))" 2>/dev/null)
        elif [ "$json_path" = ".web.client_secret" ]; then
            result=$(python3 -c "import json; data = json.load(open('$json_file')); print(data.get('web', {}).get('client_secret', ''))" 2>/dev/null)
        elif [ "$json_path" = ".web.project_id" ]; then
            result=$(python3 -c "import json; data = json.load(open('$json_file')); print(data.get('web', {}).get('project_id', ''))" 2>/dev/null)
        fi
        
        if [ $? -eq 0 ] && [ -n "$result" ]; then
            echo "$result"
            return 0
        fi
    fi
    
    # Fall back to Python 2 (legacy)
    if command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
        if [ "$json_path" = ".web.client_id" ]; then
            result=$(python -c "import json; data = json.load(open('$json_file')); print(data.get('web', {}).get('client_id', ''))" 2>/dev/null)
        elif [ "$json_path" = ".web.client_secret" ]; then
            result=$(python -c "import json; data = json.load(open('$json_file')); print(data.get('web', {}).get('client_secret', ''))" 2>/dev/null)
        elif [ "$json_path" = ".web.project_id" ]; then
            result=$(python -c "import json; data = json.load(open('$json_file')); print(data.get('web', {}).get('project_id', ''))" 2>/dev/null)
        fi
        
        if [ $? -eq 0 ] && [ -n "$result" ]; then
            echo "$result"
            return 0
        fi
    fi
    
    # Last resort: basic grep/sed (less reliable but works for simple cases)
    if [ "$json_path" = ".web.client_id" ]; then
        result=$(grep -o '"client_id"[[:space:]]*:[[:space:]]*"[^"]*"' "$json_file" 2>/dev/null | sed 's/.*"client_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' | head -1)
    elif [ "$json_path" = ".web.client_secret" ]; then
        result=$(grep -o '"client_secret"[[:space:]]*:[[:space:]]*"[^"]*"' "$json_file" 2>/dev/null | sed 's/.*"client_secret"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' | head -1)
    elif [ "$json_path" = ".web.project_id" ]; then
        result=$(grep -o '"project_id"[[:space:]]*:[[:space:]]*"[^"]*"' "$json_file" 2>/dev/null | sed 's/.*"project_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' | head -1)
    fi
    
    if [ -n "$result" ]; then
        echo "$result"
        return 0
    fi
    
    return 1
}

# Map service names to Google API identifiers
get_api_name() {
    case $1 in
        gmail)
            echo "gmail.googleapis.com"
            ;;
        calendar)
            echo "calendar-json.googleapis.com"
            ;;
        drive)
            echo "drive.googleapis.com"
            ;;
        docs)
            echo "docs.googleapis.com"
            ;;
        sheets)
            echo "sheets.googleapis.com"
            ;;
        slides)
            echo "slides.googleapis.com"
            ;;
        tasks)
            echo "tasks.googleapis.com"
            ;;
        contacts)
            echo "people.googleapis.com"
            ;;
        admin)
            echo "admin.googleapis.com"
            ;;
        meet)
            echo "meet.googleapis.com"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Initialize variables
JSON_FILE=""
CLIENT_ID=""
CLIENT_SECRET=""
USER_EMAIL=""
PROJECT_ID=""
ENABLE_SERVICES=false
SKIP_GCLOUD=false
SERVICES="gmail,calendar,drive,docs,sheets,slides,tasks,contacts"

# Parse command line arguments
if [ $# -eq 0 ]; then
    print_error "No arguments provided"
    echo ""
    usage
fi

# First argument should be the JSON file
JSON_FILE="$1"
shift

# Validate JSON file exists
if [ ! -f "$JSON_FILE" ]; then
    print_error "JSON file not found: $JSON_FILE"
    exit 1
fi

# Parse remaining optional arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --user_email)
            USER_EMAIL="$2"
            shift 2
            ;;
        --enable_services)
            ENABLE_SERVICES=true
            shift
            ;;
        --services)
            SERVICES="$2"
            shift 2
            ;;
        --skip_gcloud)
            SKIP_GCLOUD=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown argument: $1"
            usage
            ;;
    esac
done

# Extract values from JSON file
print_step "Reading credentials from JSON file: $JSON_FILE"

CLIENT_ID=$(extract_json_value "$JSON_FILE" ".web.client_id")
if [ -z "$CLIENT_ID" ] || [ "$CLIENT_ID" = "null" ]; then
    print_error "Failed to extract client_id from JSON file"
    print_info "Make sure the JSON file has the structure: {\"web\": {\"client_id\": \"...\"}}"
    exit 1
fi

CLIENT_SECRET=$(extract_json_value "$JSON_FILE" ".web.client_secret")
if [ -z "$CLIENT_SECRET" ] || [ "$CLIENT_SECRET" = "null" ]; then
    print_error "Failed to extract client_secret from JSON file"
    print_info "Make sure the JSON file has the structure: {\"web\": {\"client_secret\": \"...\"}}"
    exit 1
fi

PROJECT_ID=$(extract_json_value "$JSON_FILE" ".web.project_id")
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "null" ]; then
    print_info "project_id not found in JSON file (optional, required only for --enable_services)"
else
    print_success "Extracted project_id: $PROJECT_ID"
fi

print_success "Extracted client_id: ${CLIENT_ID:0:20}..."
print_success "Extracted client_secret: ${CLIENT_SECRET:0:10}..."

# Validate user_email is provided
if [ -z "$USER_EMAIL" ]; then
    print_error "User email is required. Please provide --user_email argument."
    echo ""
    usage
fi

print_success "All required credentials extracted"

# Function to install gcloud CLI
install_gcloud() {
    print_step "Installing gcloud CLI..."
    
    # Detect OS
    OS_TYPE=$(uname -s)
    ARCH=$(uname -m)
    
    case "$OS_TYPE" in
        Darwin*)
            # macOS
            print_info "Detected macOS"
            
            # Check if Homebrew is installed
            if command -v brew &> /dev/null; then
                print_info "Installing gcloud CLI via Homebrew..."
                if brew install --cask google-cloud-sdk; then
                    print_success "gcloud CLI installed successfully via Homebrew"
                    
                    # Source gcloud path for current session
                    if [ -f "/opt/homebrew/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.bash.inc" ]; then
                        source "/opt/homebrew/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.bash.inc"
                    elif [ -f "/usr/local/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.bash.inc" ]; then
                        source "/usr/local/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.bash.inc"
                    fi
                    
                    return 0
                else
                    print_error "Failed to install via Homebrew"
                    return 1
                fi
            else
                # Download and install manually
                print_info "Homebrew not found. Downloading gcloud CLI installer..."
                
                if [ "$ARCH" = "arm64" ]; then
                    GCLOUD_URL="https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-arm.tar.gz"
                else
                    GCLOUD_URL="https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-x86_64.tar.gz"
                fi
                
                TEMP_DIR=$(mktemp -d)
                cd "$TEMP_DIR"
                
                if curl -o google-cloud-sdk.tar.gz "$GCLOUD_URL"; then
                    tar -xzf google-cloud-sdk.tar.gz
                    ./google-cloud-sdk/install.sh --quiet --path-update true --command-completion true
                    
                    # Source gcloud path
                    if [ -f "$HOME/google-cloud-sdk/path.bash.inc" ]; then
                        source "$HOME/google-cloud-sdk/path.bash.inc"
                    fi
                    
                    cd - > /dev/null
                    rm -rf "$TEMP_DIR"
                    print_success "gcloud CLI installed successfully"
                    return 0
                else
                    cd - > /dev/null
                    rm -rf "$TEMP_DIR"
                    print_error "Failed to download gcloud CLI"
                    return 1
                fi
            fi
            ;;
            
        Linux*)
            # Linux
            print_info "Detected Linux"
            
            # Check for package manager
            if command -v apt-get &> /dev/null; then
                # Debian/Ubuntu
                print_info "Installing gcloud CLI via apt..."
                
                # Add Cloud SDK repo
                echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
                
                # Install required packages
                sudo apt-get install -y apt-transport-https ca-certificates gnupg curl
                
                # Import Google Cloud public key
                curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
                
                # Update and install
                sudo apt-get update && sudo apt-get install -y google-cloud-cli
                
                print_success "gcloud CLI installed successfully"
                return 0
                
            elif command -v yum &> /dev/null; then
                # Red Hat/CentOS/Fedora
                print_info "Installing gcloud CLI via yum..."
                
                sudo tee -a /etc/yum.repos.d/google-cloud-sdk.repo << EOM
[google-cloud-cli]
name=Google Cloud CLI
baseurl=https://packages.cloud.google.com/yum/repos/cloud-sdk-el8-x86_64
enabled=1
gpgcheck=1
repo_gpgcheck=0
gpgkey=https://packages.cloud.google.com/yum/doc/rpm-package-key.gpg
EOM

                sudo yum install -y google-cloud-cli
                
                print_success "gcloud CLI installed successfully"
                return 0
                
            else
                # Generic Linux - use snap if available
                if command -v snap &> /dev/null; then
                    print_info "Installing gcloud CLI via snap..."
                    sudo snap install google-cloud-cli --classic
                    print_success "gcloud CLI installed successfully"
                    return 0
                else
                    # Manual installation
                    print_info "Downloading gcloud CLI installer..."
                    
                    TEMP_DIR=$(mktemp -d)
                    cd "$TEMP_DIR"
                    
                    curl -o google-cloud-sdk.tar.gz https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-x86_64.tar.gz
                    tar -xzf google-cloud-sdk.tar.gz
                    ./google-cloud-sdk/install.sh --quiet --path-update true --command-completion true
                    
                    # Source gcloud path
                    if [ -f "$HOME/google-cloud-sdk/path.bash.inc" ]; then
                        source "$HOME/google-cloud-sdk/path.bash.inc"
                    fi
                    
                    cd - > /dev/null
                    rm -rf "$TEMP_DIR"
                    print_success "gcloud CLI installed successfully"
                    return 0
                fi
            fi
            ;;
            
        *)
            print_error "Unsupported operating system: $OS_TYPE"
            print_info "Please install gcloud CLI manually: https://cloud.google.com/sdk/docs/install"
            return 1
            ;;
    esac
}

# Validate gcloud CLI if not skipped
if [ "$SKIP_GCLOUD" = false ]; then
    print_step "Checking for gcloud CLI..."
    
    if command -v gcloud &> /dev/null; then
        GCLOUD_VERSION=$(gcloud version --format="value(core)" 2>/dev/null | head -n1)
        print_success "gcloud CLI is installed (version: $GCLOUD_VERSION)"
    else
        print_info "gcloud CLI is not installed"
        echo ""
        read -p "Would you like to install gcloud CLI now? (y/n): " -n 1 -r
        echo ""
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if install_gcloud; then
                print_success "gcloud CLI is now available"
                
                # Verify installation
                if command -v gcloud &> /dev/null; then
                    GCLOUD_VERSION=$(gcloud version --format="value(core)" 2>/dev/null | head -n1)
                    print_success "Verified installation (version: $GCLOUD_VERSION)"
                else
                    print_error "Installation completed but gcloud command not found in PATH"
                    print_info "Please restart your terminal and run the script again"
                    exit 1
                fi
            else
                print_error "Failed to install gcloud CLI"
                echo ""
                print_info "You can:"
                echo "  1. Install manually: https://cloud.google.com/sdk/docs/install"
                echo "  2. Run script with --skip_gcloud flag"
                exit 1
            fi
        else
            print_info "Skipping gcloud installation"
            print_info "You can run the script with --skip_gcloud flag to bypass this check"
            exit 1
        fi
    fi
    
    # Check if user is authenticated
    print_step "Checking gcloud authentication..."
    if gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -n1)
        if [ -n "$ACTIVE_ACCOUNT" ]; then
            print_success "Authenticated as: $ACTIVE_ACCOUNT"
        else
            print_info "No active gcloud account found"
            echo ""
            read -p "Would you like to authenticate now? (y/n): " -n 1 -r
            echo ""
            
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_info "Opening browser for authentication..."
                if gcloud auth login; then
                    print_success "Authentication successful"
                else
                    print_error "Authentication failed"
                    ENABLE_SERVICES=false
                fi
            else
                print_info "Skipping authentication"
                print_info "Note: Service enablement will be disabled"
                ENABLE_SERVICES=false
            fi
        fi
    fi
fi

# Handle service enablement
if [ "$ENABLE_SERVICES" = true ]; then
    if [ -z "$PROJECT_ID" ]; then
        print_error "--enable_services requires --project_id to be specified"
        exit 1
    fi
    
    if [ "$SKIP_GCLOUD" = true ]; then
        print_error "Cannot enable services when --skip_gcloud is set"
        exit 1
    fi
    
    print_step "Setting active project to: $PROJECT_ID"
    if gcloud config set project "$PROJECT_ID" &> /dev/null; then
        print_success "Project set successfully"
    else
        print_error "Failed to set project. Please verify the project ID is correct."
        exit 1
    fi
    
    echo ""
    print_step "Enabling Google Cloud APIs..."
    echo ""
    
    # Split services by comma and enable each one
    IFS=',' read -ra SERVICE_ARRAY <<< "$SERVICES"
    FAILED_SERVICES=()
    
    for service in "${SERVICE_ARRAY[@]}"; do
        # Trim whitespace
        service=$(echo "$service" | xargs)
        
        api_name=$(get_api_name "$service")
        
        if [ -z "$api_name" ]; then
            print_error "Unknown service: $service"
            FAILED_SERVICES+=("$service")
            continue
        fi
        
        print_info "Enabling $service ($api_name)..."
        
        if gcloud services enable "$api_name" 2>/dev/null; then
            print_success "$service enabled"
        else
            print_error "Failed to enable $service"
            FAILED_SERVICES+=("$service")
        fi
    done
    
    echo ""
    if [ ${#FAILED_SERVICES[@]} -gt 0 ]; then
        print_error "Failed to enable the following services: ${FAILED_SERVICES[*]}"
        echo ""
        print_info "You may need to:"
        echo "  1. Verify you have permission to enable APIs in this project"
        echo "  2. Check if billing is enabled for the project"
        echo "  3. Verify the project ID is correct"
        echo ""
    else
        print_success "All requested services have been enabled!"
        echo ""
    fi
fi

# Check if Docker or Podman is installed
print_step "Checking container runtime..."
CONTAINER_CMD=""

if command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
    print_success "Docker is installed"
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker Desktop or the Docker service."
        echo ""
        echo "On macOS: Start Docker Desktop application"
        echo "On Linux: Run 'sudo systemctl start docker'"
        exit 1
    fi
    print_success "Docker daemon is running"
    
elif command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
    print_success "Podman is installed"
    
     # Check if Podman socket service is running (systemd user service)
    if command -v systemctl &> /dev/null; then
        if systemctl --user list-unit-files podman.socket &> /dev/null; then
            if ! systemctl --user is-active --quiet podman.socket 2>/dev/null; then
                print_error "Podman socket service is not running"
                echo ""
                print_info "Please start it with: systemctl --user start podman.socket"
                print_info "Or enable it to start on boot: systemctl --user enable --now podman.socket"
                exit 1
            else
                print_success "Podman socket service is running"
            fi
        fi

    # Check if Podman service is accessible
    if ! podman info &> /dev/null; then
        print_error "Podman is not accessible. Please check your Podman installation."
        echo ""
        if command -v systemctl &> /dev/null; then
            print_info "You may need to:"
            echo "  1. Start Podman socket: systemctl --user start podman.socket"
            echo "  2. Enable Podman socket: systemctl --user enable --now podman.socket"
        fi
        exit 1
    fi
    print_success "Podman is accessible"
    
else
    print_error "Neither Docker nor Podman is installed. Please install one of them to continue."
    echo ""
    echo "Install Docker: https://docs.docker.com/get-docker/"
    echo "Install Podman: https://podman.io/getting-started/installation"
    exit 1
fi

# Check if docker-compose or podman-compose is installed
print_step "Checking compose tool..."
COMPOSE_CMD=""
COMPOSE_TYPE=""

# Function to execute compose commands (handles both plugin and standalone versions)
run_compose() {
    if [ "$COMPOSE_TYPE" = "plugin" ]; then
        # Plugin version: docker compose or podman compose
        $CONTAINER_CMD compose "$@"
    else
        # Standalone version: docker-compose or podman-compose
        $COMPOSE_CMD "$@"
    fi
}

if [ "$CONTAINER_CMD" = "docker" ]; then
    # Prefer plugin version (docker compose) - modern standard
    if docker compose version &> /dev/null; then
        COMPOSE_TYPE="plugin"
        COMPOSE_CMD="docker"  # Store base command only
        print_success "docker compose (plugin) is installed"
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_TYPE="standalone"
        COMPOSE_CMD="docker-compose"
        print_success "docker-compose (standalone) is installed"
    else
        print_error "docker compose is not installed. Please install it to continue."
        echo ""
        echo "Install Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
else
    # Podman: prefer plugin version (podman compose) if available
    if podman compose version &> /dev/null 2>&1; then
        COMPOSE_TYPE="plugin"
        COMPOSE_CMD="podman"  # Store base command only
        print_success "podman compose (plugin) is installed"
    elif command -v podman-compose &> /dev/null; then
        COMPOSE_TYPE="standalone"
        COMPOSE_CMD="podman-compose"
        print_success "podman-compose (standalone) is installed"
    else
        print_error "podman compose is not installed. Please install it to continue."
        echo ""
        echo "Install podman-compose: https://github.com/containers/podman-compose"
        exit 1
    fi
fi

# Define repository details
REPO_URL="https://github.com/taylorwilsdon/google_workspace_mcp.git"
REPO_DIR="google_workspace_mcp"

echo ""
print_step "Cloning repository from $REPO_URL..."

# Check if directory already exists
if [ -d "$REPO_DIR" ]; then
    print_info "Directory '$REPO_DIR' already exists. Removing it..."
    rm -rf "$REPO_DIR"
fi

# Clone the repository
if git clone "$REPO_URL" 2>/dev/null; then
    print_success "Repository cloned successfully"
else
    print_error "Failed to clone repository from $REPO_URL"
    exit 1
fi

# Validate that the repository directory exists
if [ ! -d "$REPO_DIR" ]; then
    print_error "Repository directory '$REPO_DIR' does not exist after cloning"
    exit 1
fi

print_success "Repository directory validated"

# Change to repository directory
cd "$REPO_DIR"
print_info "Changed to directory: $(pwd)"

# Create .env file
echo ""
print_step "Creating .env file..."

cat > .env << EOF
GOOGLE_OAUTH_CLIENT_ID=$CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET=$CLIENT_SECRET
USER_GOOGLE_EMAIL="$USER_EMAIL"
EOF

if [ $? -eq 0 ]; then
    print_success ".env file created successfully"
else
    print_error "Failed to create .env file"
    exit 1
fi

# Display .env contents (masked for security)
print_info ".env file contents:"
echo "----------------------------------------"
echo "GOOGLE_OAUTH_CLIENT_ID=${CLIENT_ID:0:10}..."
echo "GOOGLE_OAUTH_CLIENT_SECRET=${CLIENT_SECRET:0:10}..."
echo "USER_GOOGLE_EMAIL=\"$USER_EMAIL\""
echo "----------------------------------------"

# Detect local IP address
echo ""
print_step "Detecting local IP address..."
LOCAL_IP=""

# Try different methods to get the local IP
if command -v ipconfig &> /dev/null; then
    # macOS method
    LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "")
elif command -v hostname &> /dev/null; then
    # Linux/Unix method
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "")
fi

# Fallback: try to get IP from network interfaces
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(ip route get 1 2>/dev/null | awk '{print $7; exit}' || echo "")
fi

# If still no IP found, use localhost
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="localhost"
    print_info "Could not detect local IP, using localhost"
else
    print_success "Detected local IP: $LOCAL_IP"
fi

# Run docker-compose up in detached mode
echo ""
print_step "Starting Google Workspace MCP Server..."
echo ""

if run_compose up -d; then
    echo ""
    print_success "🚀 Google Workspace MCP Server is now running in the background!"
    echo ""
    print_info "Server Details:"
    echo "  • SSE Endpoint: http://$LOCAL_IP:8000/mcp"
    echo "  • OAuth Callback: http://$LOCAL_IP:8000/oauth2callback"
    echo ""
    print_info "Useful Commands:"
    if [ "$COMPOSE_TYPE" = "plugin" ]; then
        echo "  • View logs:        $CONTAINER_CMD compose logs -f"
        echo "  • Stop server:      $CONTAINER_CMD compose down"
        echo "  • Restart server:   $CONTAINER_CMD compose restart"
        echo "  • View status:      $CONTAINER_CMD compose ps"
    else
        echo "  • View logs:        $COMPOSE_CMD logs -f"
        echo "  • Stop server:      $COMPOSE_CMD down"
        echo "  • Restart server:   $COMPOSE_CMD restart"
        echo "  • View status:      $COMPOSE_CMD ps"
    fi
    echo ""
    
    if [ "$ENABLE_SERVICES" = true ]; then
        print_success "Google Cloud APIs have been enabled for project: $PROJECT_ID"
        echo ""
    fi
else
    print_error "Failed to start the server"
    exit 1
fi

