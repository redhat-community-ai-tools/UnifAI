#!/bin/bash

# Stress Test Runner Script
# =========================
# This script helps run the document upload stress test with various configurations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:13457/api}"
MONGODB_HOST="${MONGODB_HOST:-localhost}"
MONGODB_PORT="${MONGODB_PORT:-27017}"
MONGODB_DB="${MONGODB_DB:-celery}"

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_dependencies() {
    print_header "Checking Dependencies"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    print_success "Python 3 found: $(python3 --version)"
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 is not installed"
        exit 1
    fi
    print_success "pip3 found"
    
    # Check if required packages are installed
    print_info "Checking Python packages..."
    if ! python3 -c "import aiohttp" 2>/dev/null; then
        print_warning "aiohttp not found - installing dependencies..."
        pip3 install -r requirements_stress_test.txt
    else
        print_success "Required Python packages found"
    fi
    
    echo ""
}

check_services() {
    print_header "Checking Services"
    
    # Check backend API
    print_info "Checking backend API at $API_BASE_URL..."
    if curl -s --max-time 5 "${API_BASE_URL%/api}/health" > /dev/null 2>&1; then
        print_success "Backend API is responding"
    else
        print_error "Backend API is not responding at $API_BASE_URL"
        print_info "Make sure the backend server is running"
        exit 1
    fi
    
    # Check MongoDB
    print_info "Checking MongoDB at $MONGODB_HOST:$MONGODB_PORT..."
    if command -v mongosh &> /dev/null; then
        if mongosh --host "$MONGODB_HOST" --port "$MONGODB_PORT" --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; then
            print_success "MongoDB is accessible"
        else
            print_error "MongoDB is not accessible at $MONGODB_HOST:$MONGODB_PORT"
            exit 1
        fi
    elif command -v mongo &> /dev/null; then
        if mongo --host "$MONGODB_HOST" --port "$MONGODB_PORT" --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; then
            print_success "MongoDB is accessible"
        else
            print_error "MongoDB is not accessible at $MONGODB_HOST:$MONGODB_PORT"
            exit 1
        fi
    else
        print_warning "MongoDB client not found - skipping MongoDB check"
        print_info "Install mongosh or mongo to enable MongoDB health checks"
    fi
    
    echo ""
}

print_configuration() {
    print_header "Test Configuration"
    echo "API Base URL:  $API_BASE_URL"
    echo "MongoDB Host:  $MONGODB_HOST"
    echo "MongoDB Port:  $MONGODB_PORT"
    echo "MongoDB DB:    $MONGODB_DB"
    echo ""
}

run_test() {
    print_header "Starting Stress Test"
    print_info "Test logs will be saved with timestamp"
    print_info "Press Ctrl+C to stop the test"
    echo ""
    
    export API_BASE_URL
    export MONGODB_HOST
    export MONGODB_PORT
    export MONGODB_DB
    
    python3 stress_test_doc_upload.py
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo ""
        print_success "Stress test completed successfully!"
    else
        echo ""
        print_error "Stress test failed with exit code $exit_code"
        exit $exit_code
    fi
}

show_help() {
    cat << EOF
Document Upload Stress Test Runner

Usage: $0 [OPTIONS]

OPTIONS:
    -h, --help              Show this help message
    -c, --check-only        Only check dependencies and services, don't run test
    -s, --skip-checks       Skip pre-flight checks and run test directly
    --api-url URL           Set API base URL (default: http://localhost:13457/api)
    --mongo-host HOST       Set MongoDB host (default: localhost)
    --mongo-port PORT       Set MongoDB port (default: 27017)
    --mongo-db DB           Set MongoDB database (default: celery)

EXAMPLES:
    # Run with default configuration
    $0

    # Run with custom API URL
    $0 --api-url http://192.168.1.100:13457/api

    # Check services without running test
    $0 --check-only

    # Run with all custom settings
    $0 --api-url http://api.example.com:13457/api \\
       --mongo-host mongodb.example.com \\
       --mongo-port 27017

ENVIRONMENT VARIABLES:
    API_BASE_URL            API base URL
    MONGODB_HOST            MongoDB hostname
    MONGODB_PORT            MongoDB port
    MONGODB_DB              MongoDB database name

EOF
}

# Parse command line arguments
CHECK_ONLY=false
SKIP_CHECKS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -c|--check-only)
            CHECK_ONLY=true
            shift
            ;;
        -s|--skip-checks)
            SKIP_CHECKS=true
            shift
            ;;
        --api-url)
            API_BASE_URL="$2"
            shift 2
            ;;
        --mongo-host)
            MONGODB_HOST="$2"
            shift 2
            ;;
        --mongo-port)
            MONGODB_PORT="$2"
            shift 2
            ;;
        --mongo-db)
            MONGODB_DB="$2"
            shift 2
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_header "Document Upload Stress Test"
    echo ""
    
    if [ "$SKIP_CHECKS" = false ]; then
        check_dependencies
        print_configuration
        check_services
    else
        print_warning "Skipping pre-flight checks"
        print_configuration
    fi
    
    if [ "$CHECK_ONLY" = true ]; then
        print_success "Pre-flight checks completed successfully"
        print_info "Run without --check-only to execute the stress test"
        exit 0
    fi
    
    run_test
}

# Run main function
main

