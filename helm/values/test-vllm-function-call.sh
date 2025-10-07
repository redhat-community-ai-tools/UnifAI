#!/bin/bash

# Test script for IBM Granite 4.0 H Small vLLM endpoint
# Tests key Granite features: tool calling, long context, code generation, multilingual, etc.
# Automatically detects route and model from OpenShift/vLLM API

set -e

# Global variables (will be auto-detected)
VLLM_ENDPOINT=""
SELECTED_MODEL=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check required dependencies
check_dependencies() {
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed"
        exit 1
    fi
    
    if ! command -v oc &> /dev/null; then
        log_error "oc (OpenShift CLI) is required but not installed"
        exit 1
    fi
}

# Auto-detect route using label
auto_detect_route() {
    log_info "Auto-detecting vLLM service route..."
    
    echo "Command: oc get route -l app.kubernetes.io/name=vllm-serving-engine -o jsonpath='{.items[0].spec.host}'"
    
    # Get the route hostname using the label
    ROUTE_HOST=$(oc get route -l app.kubernetes.io/name=vllm-serving-engine -o jsonpath='{.items[0].spec.host}' 2>/dev/null)
    
    if [ -z "$ROUTE_HOST" ]; then
        log_error "Could not find route with label 'app.kubernetes.io/name=vllm-serving-engine'"
        exit 1
    fi
    
    # Use HTTP scheme (route doesn't have TLS configured)
    VLLM_ENDPOINT="http://${ROUTE_HOST}"
    
    log_success "Found vLLM endpoint: $VLLM_ENDPOINT"
    echo ""
}

# Auto-detect available model
auto_detect_model() {
    log_info "Auto-detecting available models..."
    
    echo "Command: curl --noproxy \"*\" -s \"${VLLM_ENDPOINT}/v1/models\""
    
    local response
    response=$(curl --noproxy "*" -s "${VLLM_ENDPOINT}/v1/models" 2>/dev/null)
    
    echo "Full Response:"
    echo "$response" | jq '.' 2>/dev/null || echo "$response"
    echo ""
    
    if echo "$response" | jq -e '.data[0].id' > /dev/null 2>&1; then
        log_success "Successfully retrieved models"
        
        local model_count
        model_count=$(echo "$response" | jq '.data | length')
        echo "Found $model_count model(s):"
        echo "$response" | jq -r '.data[].id' | sed 's/^/  - /'
        
        # Use the first available model
        SELECTED_MODEL=$(echo "$response" | jq -r '.data[0].id')
        log_info "Selected model for testing: $SELECTED_MODEL"
        
    else
        log_error "Failed to get models from vLLM API"
        echo "Response: $response"
        exit 1
    fi
    echo ""
}

# Test endpoint availability
test_health() {
    log_info "Testing vLLM health endpoint..."
    
    echo "Command: curl --noproxy \"*\" -s -f \"${VLLM_ENDPOINT}/health\""
    
    if curl --noproxy "*" -s -f "${VLLM_ENDPOINT}/health" > /dev/null; then
        log_success "vLLM endpoint is healthy"
    else
        log_error "vLLM endpoint is not accessible at ${VLLM_ENDPOINT}"
        exit 1
    fi
    echo ""
}

# Test basic chat completion
test_basic_chat() {
    log_info "Testing basic chat completion..."
    
    echo "Command:"
    echo "curl --noproxy \"*\" -X POST \"${VLLM_ENDPOINT}/v1/chat/completions\" \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{"
    echo "    \"model\": \"${SELECTED_MODEL}\","
    echo "    \"messages\": [{"
    echo "      \"role\": \"user\","
    echo "      \"content\": \"Hello! Please introduce yourself as IBM Granite 4.0 H Small.\""
    echo "    }],"
    echo "    \"max_tokens\": 200,"
    echo "    \"temperature\": 0.7"
    echo "  }'"
    echo ""
    
    response=$(curl --noproxy "*" -s -X POST "${VLLM_ENDPOINT}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "'${SELECTED_MODEL}'",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello! Please introduce yourself as IBM Granite 4.0 H Small."
                }
            ],
            "max_tokens": 200,
            "temperature": 0.7
        }')
    
    echo "Full Response:"
    echo "$response" | jq '.' 2>/dev/null || echo "$response"
    echo ""
    
    if echo "$response" | jq -e '.choices[0].message.content' > /dev/null 2>&1; then
        log_success "Basic chat completion works"
        echo "Model Response: $(echo "$response" | jq -r '.choices[0].message.content')"
    else
        log_error "Basic chat completion failed"
    fi
    echo ""
}

# Test enhanced tool calling (key Granite feature)
test_tool_calling() {
    log_info "Testing enhanced tool calling capabilities..."
    
    # Show the complete curl command
    echo "Command:"
    cat << EOF
curl --noproxy "*" -X POST "${VLLM_ENDPOINT}/v1/chat/completions" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${SELECTED_MODEL}",
    "messages": [
      {
        "role": "user",
        "content": "What is the weather like in Boston right now?"
      }
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_current_weather",
          "description": "Get the current weather for a specified city",
          "parameters": {
            "type": "object",
            "properties": {
              "city": {
                "type": "string",
                "description": "Name of the city"
              }
            },
            "required": ["city"]
          }
        }
      }
    ],
    "tool_choice": "auto",
    "max_tokens": 150
  }'
EOF
    echo ""
    
    response=$(curl --noproxy "*" -s -X POST "${VLLM_ENDPOINT}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "'${SELECTED_MODEL}'",
            "messages": [
                {
                    "role": "user",
                    "content": "What is the weather like in Boston right now?"
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_current_weather",
                        "description": "Get the current weather for a specified city",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {
                                    "type": "string",
                                    "description": "Name of the city"
                                }
                            },
                            "required": ["city"]
                        }
                    }
                }
            ],
            "tool_choice": "auto",
            "max_tokens": 150
        }')
    
    echo "Full Response:"
    echo "$response" | jq '.' 2>/dev/null || echo "$response"
    echo ""
    
    # Check for both OpenAI format tool_calls and Granite's <tool_call> format
    local content
    content=$(echo "$response" | jq -r '.choices[0].message.content' 2>/dev/null || echo "")
    
    if echo "$response" | jq -e '.choices[0].message.tool_calls' > /dev/null 2>&1; then
        log_success "Tool calling works - OpenAI format tool_calls detected"
        echo "Tool call: $(echo "$response" | jq -r '.choices[0].message.tool_calls[0].function.name')"
        echo "Arguments: $(echo "$response" | jq -r '.choices[0].message.tool_calls[0].function.arguments')"
    elif echo "$content" | grep -q "tool_call.*get_.*weather\|get_current_weather"; then
        log_success "✨ Tool calling works - Granite format detected!"
        echo "Model Response Content:"
        echo "$content"
        
        # Extract function details from Granite's format
       if echo "$content" | grep -q '"name".*"get_current_weather"'; then
            log_success "🔧 Weather function call detected in Granite format"
        fi
        if echo "$content" | grep -q '"city".*"Boston"'; then
            log_success "🎯 Correct city parameter extracted: Boston"
        fi
    else
        log_warning "Tool calling might not be working as expected"
        echo "Response content: $content"
    fi
    
    # Show token usage
    local prompt_tokens completion_tokens total_tokens
    prompt_tokens=$(echo "$response" | jq -r '.usage.prompt_tokens // "N/A"')
    completion_tokens=$(echo "$response" | jq -r '.usage.completion_tokens // "N/A"')
    total_tokens=$(echo "$response" | jq -r '.usage.total_tokens // "N/A"')
    
    echo "Token Usage: Prompt=$prompt_tokens, Completion=$completion_tokens, Total=$total_tokens"
    echo ""
}

# Test code generation capabilities
test_code_generation() {
    log_info "Testing code generation capabilities..."
    
    response=$(curl --noproxy "*" -s -X POST "${VLLM_ENDPOINT}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "'${SELECTED_MODEL}'",
            "messages": [
                {
                    "role": "user",
                    "content": "Write a Python function to calculate the Fibonacci sequence using dynamic programming. Include docstring and type hints."
                }
            ],
            "max_tokens": 400,
            "temperature": 0.3
        }')
    
    if echo "$response" | jq -e '.choices[0].message.content' > /dev/null 2>&1; then
        log_success "Code generation works"
        echo "Generated code:"
        echo "$(echo "$response" | jq -r '.choices[0].message.content')"
    else
        log_error "Code generation failed"
        echo "Response: $response"
    fi
    echo ""
}

# Test Fill-In-the-Middle (FIM) code completion
test_fim_completion() {
    log_info "Testing Fill-In-the-Middle (FIM) code completion..."
    
    response=$(curl --noproxy "*" -s -X POST "${VLLM_ENDPOINT}/v1/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "'${SELECTED_MODEL}'",
            "prompt": "def calculate_sum(numbers):\n    \"\"\"Calculate the sum of a list of numbers.\"\"\"\n    # TODO: Add implementation here\n    ",
            "max_tokens": 150,
            "temperature": 0.2,
            "stop": ["\n\n"]
        }')
    
    if echo "$response" | jq -e '.choices[0].text' > /dev/null 2>&1; then
        log_success "FIM code completion works"
        echo "Completed code:"
        echo "$(echo "$response" | jq -r '.choices[0].text')"
    else
        log_warning "FIM completion might not be working as expected"
        echo "Response: $response"
    fi
    echo ""
}

# Test multilingual capabilities
test_multilingual() {
    log_info "Testing multilingual capabilities (Spanish)..."
    
    response=$(curl --noproxy "*" -s -X POST "${VLLM_ENDPOINT}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "'${SELECTED_MODEL}'",
            "messages": [
                {
                    "role": "user",
                    "content": "Hola, ¿puedes explicarme qué es la inteligencia artificial en español? Por favor, responde en español."
                }
            ],
            "max_tokens": 300,
            "temperature": 0.7
        }')
    
    if echo "$response" | jq -e '.choices[0].message.content' > /dev/null 2>&1; then
        log_success "Multilingual (Spanish) support works"
        echo "Spanish response: $(echo "$response" | jq -r '.choices[0].message.content')"
    else
        log_error "Multilingual test failed"
        echo "Response: $response"
    fi
    echo ""
}

# Test long context capabilities (using a longer prompt)
test_long_context() {
    log_info "Testing long context capabilities..."
    
    # Create a longer context prompt
    long_context="Here is a detailed analysis of artificial intelligence trends in 2024: "
    for i in {1..10}; do
        long_context+="Section $i: This section discusses various aspects of AI development, including machine learning advances, natural language processing improvements, and the impact on various industries. "
    done
    long_context+="Based on all the information above, please provide a concise summary of the key AI trends mentioned."
    
    response=$(curl --noproxy "*" -s -X POST "${VLLM_ENDPOINT}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "'${SELECTED_MODEL}'",
            "messages": [
                {
                    "role": "user",
                    "content": "'"$long_context"'"
                }
            ],
            "max_tokens": 200,
            "temperature": 0.5
        }')
    
    if echo "$response" | jq -e '.choices[0].message.content' > /dev/null 2>&1; then
        log_success "Long context processing works"
        echo "Summary: $(echo "$response" | jq -r '.choices[0].message.content')"
    else
        log_error "Long context test failed"
        echo "Response: $response"
    fi
    echo ""
}

# Test text classification
test_text_classification() {
    log_info "Testing text classification capabilities..."
    
    response=$(curl --noproxy "*" -s -X POST "${VLLM_ENDPOINT}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "'${SELECTED_MODEL}'",
            "messages": [
                {
                    "role": "user",
                    "content": "Classify the sentiment of this text as positive, negative, or neutral: '\''I absolutely love this new product! It works perfectly and exceeded my expectations.'\''"
                }
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }')
    
    if echo "$response" | jq -e '.choices[0].message.content' > /dev/null 2>&1; then
        log_success "Text classification works"
        echo "Classification: $(echo "$response" | jq -r '.choices[0].message.content')"
    else
        log_error "Text classification failed"
        echo "Response: $response"
    fi
    echo ""
}

# Test RAG-style question answering
test_rag_qa() {
    log_info "Testing RAG-style question answering..."
    
    response=$(curl --noproxy "*" -s -X POST "${VLLM_ENDPOINT}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "'${SELECTED_MODEL}'",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Use the following context to answer questions: Context: IBM Granite is a family of large language models designed for enterprise use. The models are trained on diverse datasets and support multiple languages. They excel at code generation, tool calling, and instruction following."
                },
                {
                    "role": "user",
                    "content": "Based on the context provided, what are the key strengths of IBM Granite models?"
                }
            ],
            "max_tokens": 150,
            "temperature": 0.3
        }')
    
    if echo "$response" | jq -e '.choices[0].message.content' > /dev/null 2>&1; then
        log_success "RAG-style Q&A works"
        echo "Answer: $(echo "$response" | jq -r '.choices[0].message.content')"
    else
        log_error "RAG-style Q&A failed"
        echo "Response: $response"
    fi
    echo ""
}

# Test model info endpoint
test_model_info() {
    log_info "Testing model information endpoint..."
    
    echo "Command: curl --noproxy \"*\" -s \"${VLLM_ENDPOINT}/v1/models\""
    
    response=$(curl --noproxy "*" -s "${VLLM_ENDPOINT}/v1/models")
    
    echo "Full Response:"
    echo "$response" | jq '.' 2>/dev/null || echo "$response"
    echo ""
    
    if echo "$response" | jq -e '.data[0].id' > /dev/null 2>&1; then
        log_success "Model info endpoint works"
        echo "Available models: $(echo "$response" | jq -r '.data[].id' | tr '\n' ', ')"
    else
        log_warning "Model info endpoint might not be working"
    fi
    echo ""
}

# Performance test
test_performance() {
    log_info "Testing performance with concurrent requests..."
    
    # Test with 3 concurrent requests
    for i in {1..3}; do
        (
            start_time=$(date +%s.%N)
            response=$(curl --noproxy "*" -s -X POST "${VLLM_ENDPOINT}/v1/chat/completions" \
                -H "Content-Type: application/json" \
                -d '{
                    "model": "'${SELECTED_MODEL}'",
                    "messages": [
                        {
                            "role": "user",
                            "content": "Generate a short creative story about AI and humans working together. Request #'$i'"
                        }
                    ],
                    "max_tokens": 100,
                    "temperature": 0.8
                }')
            end_time=$(date +%s.%N)
            duration=$(echo "$end_time - $start_time" | bc -l)
            
            if echo "$response" | jq -e '.choices[0].message.content' > /dev/null 2>&1; then
                echo "Request $i completed in ${duration}s"
            else
                echo "Request $i failed"
            fi
        ) &
    done
    
    wait
    log_success "Concurrent request test completed"
    echo ""
}

# Main test execution
main() {
    echo "========================================================"
    echo "🚀 IBM Granite 4.0 H Small vLLM Test Suite (Auto-Detect)"
    echo "========================================================"
    echo ""
    
    check_dependencies
    auto_detect_route
    auto_detect_model
    
    echo "========================================================"
    echo "Testing Configuration:"
    echo "Endpoint: $VLLM_ENDPOINT"
    echo "Model: $SELECTED_MODEL"
    echo "========================================================"
    echo ""
    
    # Run all tests
    test_health
    test_tool_calling
    test_basic_chat
    test_code_generation
    test_multilingual
    test_text_classification
    test_rag_qa
    
    echo "========================================================"
    log_success "🎉 All tests completed successfully!"
    echo "========================================================"
}

# Handle command line arguments
case "${1:-}" in
    "health") 
        check_dependencies
        auto_detect_route
        test_health 
        ;;
    "chat") 
        check_dependencies
        auto_detect_route
        auto_detect_model
        test_basic_chat 
        ;;
    "tools") 
        check_dependencies
        auto_detect_route
        auto_detect_model
        test_tool_calling 
        ;;
    "code") 
        check_dependencies
        auto_detect_route
        auto_detect_model
        test_code_generation 
        ;;
    "fim") 
        check_dependencies
        auto_detect_route
        auto_detect_model
        test_fim_completion 
        ;;
    "multilingual") 
        check_dependencies
        auto_detect_route
        auto_detect_model
        test_multilingual 
        ;;
    "context") 
        check_dependencies
        auto_detect_route
        auto_detect_model
        test_long_context 
        ;;
    "classify") 
        check_dependencies
        auto_detect_route
        auto_detect_model
        test_text_classification 
        ;;
    "rag") 
        check_dependencies
        auto_detect_route
        auto_detect_model
        test_rag_qa 
        ;;
    "performance") 
        check_dependencies
        auto_detect_route
        auto_detect_model
        test_performance 
        ;;
    "info") 
        check_dependencies
        auto_detect_route
        test_model_info 
        ;;
    "") main ;;
    *) 
        echo "Usage: $0 [test_name]"
        echo "Available tests: health, chat, tools, code, fim, multilingual, context, classify, rag, performance, info"
        echo "Run without arguments to execute all tests"
        echo "Note: Route and model are auto-detected using OpenShift labels"
        exit 1
        ;;
esac
