# IBM Granite 4.0 H Small vLLM Test Suite

A comprehensive testing script for IBM Granite 4.0 H Small model deployed on vLLM serving engine in OpenShift environments.

## 🚀 Features

### **Automated Discovery**
- **Auto-detects OpenShift routes** using Kubernetes labels
- **Auto-discovers available models** from vLLM API
- **Zero manual configuration** required

### **Comprehensive Testing**
- **Enhanced Tool Calling** - Tests Granite's signature function calling capabilities
- **Code Generation** - Python functions with type hints and docstrings
- **Fill-In-the-Middle (FIM)** - Code completion capabilities
- **Multilingual Support** - Spanish language testing
- **Long Context Processing** - Extended context handling (64K tokens)
- **Text Classification** - Sentiment analysis capabilities
- **RAG-style Q&A** - Context-based question answering
- **Performance Testing** - Concurrent request handling

### **Enterprise-Ready**
- **Corporate proxy support** with `--noproxy "*"` handling
- **Complete command visibility** - Shows exact curl commands
- **Full response logging** - JSON formatted outputs
- **Error handling** - Robust failure detection and reporting

## 📋 Prerequisites

### **Required Tools**
- `curl` - HTTP client for API requests
- `jq` - JSON processor for response parsing
- `oc` - OpenShift CLI for route discovery

### **OpenShift Environment**
- Deployed vLLM serving engine with Granite 4.0 H Small model
- Route labeled with `app.kubernetes.io/name=vllm-serving-engine`
- Access to the OpenShift cluster (authenticated `oc` session)

### **Network Requirements**
- Access to OpenShift routes
- Corporate proxy bypass capability (script uses `--noproxy "*"`)

## ⚙️ Installation

1. **Download the script:**
   ```bash
   # Script should be in your project directory
   ls test-granite-vllm.sh
   ```

2. **Make executable:**
   ```bash
   chmod +x test-granite-vllm.sh
   ```

3. **Verify dependencies:**
   ```bash
   # Check required tools are installed
   which curl jq oc
   ```

## 🎯 Usage

### **Run All Tests (Recommended)**
```bash
./test-granite-vllm.sh
```

### **Run Individual Tests**
```bash
# Test function calling only
./test-granite-vllm.sh tools

# Test basic chat
./test-granite-vllm.sh chat

# Test code generation
./test-granite-vllm.sh code

# Test multilingual capabilities
./test-granite-vllm.sh multilingual

# Health check only
./test-granite-vllm.sh health
```

### **Available Test Options**
| Command | Description |
|---------|-------------|
| `health` | Endpoint health check |
| `chat` | Basic conversation test |
| `tools` | Enhanced tool calling test |
| `code` | Python code generation |
| `fim` | Fill-in-the-middle completion |
| `multilingual` | Spanish language support |
| `context` | Long context processing |
| `classify` | Text classification |
| `rag` | RAG-style question answering |
| `performance` | Concurrent request testing |
| `info` | Model information endpoint |

## 📊 Expected Output

### **Successful Execution Example**
```bash
🚀 IBM Granite 4.0 H Small vLLM Test Suite (Auto-Detect)
========================================================

[INFO] Auto-detecting vLLM service route...
Command: oc get route -l app.kubernetes.io/name=vllm-serving-engine -o jsonpath='{.items[0].spec.host}'
[SUCCESS] Found vLLM endpoint: http://granite-vllm-serving-engine-tag-ai--runtime-int.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com

[INFO] Auto-detecting available models...
Command: curl --noproxy "*" -s "http://granite-vllm.../v1/models"
Full Response:
{
  "object": "list",
  "data": [
    {
      "id": "/models/.cache/models--ibm-granite-granite-4.0-h-small",
      "object": "model",
      "created": 1759771800,
      "owned_by": "vllm"
    }
  ]
}

[SUCCESS] Successfully retrieved models
Found 1 model(s):
  - /models/.cache/models--ibm-granite-granite-4.0-h-small
[INFO] Selected model for testing: /models/.cache/models--ibm-granite-granite-4.0-h-small

========================================================
Testing Configuration:
Endpoint: http://granite-vllm-serving-engine-tag-ai--runtime-int.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com
Model: /models/.cache/models--ibm-granite-granite-4.0-h-small
========================================================

[INFO] Testing vLLM health endpoint...
[SUCCESS] vLLM endpoint is healthy

[INFO] Testing enhanced tool calling capabilities...
Command:
curl --noproxy "*" -X POST "http://granite-vllm-serving-engine.../v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/models/.cache/models--ibm-granite-granite-4.0-h-small",
    "messages": [...],
    "tools": [...],
    "tool_choice": "auto",
    "max_tokens": 150
  }'

Full Response:
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "choices": [{
    "message": {
      "content": "<tool_call>\n{\"name\": \"get_current_weather\", \"arguments\": {\"city\": \"Boston\"}}\n</tool_call>"
    }
  }],
  "usage": {
    "prompt_tokens": 203,
    "completion_tokens": 21,
    "total_tokens": 224
  }
}

[SUCCESS] ✨ Tool calling works - Granite format detected!
[SUCCESS] 🔧 Weather function call detected in Granite format
[SUCCESS] 🎯 Correct city parameter extracted: Boston
Token Usage: Prompt=203, Completion=21, Total=224
```

## 🔧 Technical Details

### **Route Discovery**
The script uses OpenShift labels to automatically find the vLLM service route:
```bash
oc get route -l app.kubernetes.io/name=vllm-serving-engine -o jsonpath='{.items[0].spec.host}'
```

### **Model Discovery**
Queries the vLLM `/v1/models` endpoint to find available models:
```bash
curl --noproxy "*" -s "${VLLM_ENDPOINT}/v1/models"
```

### **Granite Tool Calling Format**
Granite 4.0 H Small uses its own tool calling format:
```xml
<tool_call>
{"name": "function_name", "arguments": {"param": "value"}}
</tool_call>
```

### **Corporate Proxy Handling**
All requests use `--noproxy "*"` to bypass corporate proxy settings that may interfere with internal cluster communication.

## 🚨 Troubleshooting

### **Common Issues**

#### **"Route not found"**
```bash
# Check if route exists with correct label
oc get route -l app.kubernetes.io/name=vllm-serving-engine
oc describe route granite-vllm-serving-engine
```

#### **"Application is not available"**
```bash
# Check pod status
oc get pods -l app.kubernetes.io/name=vllm-serving-engine
oc logs -f granite-vllm-serving-engine-<pod-id>
```

#### **"No models found"**
```bash
# Check if vLLM is fully started
oc logs granite-vllm-serving-engine-<pod-id> --tail=20
# Wait for model loading to complete
```

#### **"Proxy resolution errors"**
```bash
# The script already handles proxy issues
# If problems persist, check corporate firewall settings
export no_proxy="*"
```

### **Debug Mode**
Run with verbose output:
```bash
# Enable bash debug mode
bash -x ./test-granite-vllm.sh tools
```

## 📈 Performance Expectations

### **Model Capabilities Tested**

| Feature | Test Type | Expected Response Time |
|---------|-----------|----------------------|
| **Tool Calling** | Function detection & parsing | 2-4 seconds |
| **Code Generation** | Python function creation | 3-6 seconds |
| **Chat** | Basic conversation | 1-2 seconds |
| **Multilingual** | Spanish response | 2-4 seconds |
| **Classification** | Sentiment analysis | 1-2 seconds |

### **Hardware Configuration**
- **2x 40GB GPUs** with tensor parallelism
- **64K token context** length
- **32B parameters** (9B active via MoE)
- **No quantization** (full precision BF16)

## 🎯 Key Granite 4.0 H Small Features

### **Enhanced Tool Calling**
Unlike standard models, Granite 4.0 H Small has **superior function calling** capabilities:
- More accurate function detection
- Better parameter extraction
- Enhanced reasoning about when to use tools

### **MoE Architecture**  
- **32B total parameters** but only **9B active** during inference
- Efficient resource usage while maintaining large model capabilities
- Hybrid attention + Mamba2 architecture for optimal performance

### **Enterprise Focus**
- **Instruction following** optimized for business applications
- **Multilingual support** (12+ languages)
- **Code intelligence** with multiple programming languages
- **128K native context** length (reduced to 64K for GPU constraints)

## 📚 References

- **IBM Granite 4.0 Models**: [Hugging Face Collection](https://huggingface.co/collections/ibm-granite/granite-4.0-language-models-6702e3b26f85b30b9ab4df32)
- **vLLM Documentation**: [vLLM OpenAI API](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html)
- **OpenShift Routes**: [Red Hat Documentation](https://docs.openshift.com/container-platform/latest/networking/routes/route-configuration.html)

## 🏆 Success Criteria

✅ **Deployment Successful When:**
- Route auto-detection finds valid endpoint
- Model API returns cached model path
- Health endpoint responds with 200 OK
- Tool calling test generates proper function calls
- All API responses are valid JSON with expected structure

---

**Happy Testing!** 🚀

For issues or improvements, check the vLLM serving engine logs and OpenShift route configuration.
