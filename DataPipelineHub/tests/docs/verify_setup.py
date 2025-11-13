#!/usr/bin/env python3
"""
Setup Verification Script
=========================
Verifies that all dependencies and services are properly configured
before running the stress test.
"""

import sys
import os
import importlib.util
from typing import List, Tuple

# Color codes
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color


def print_header(text: str):
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}{text}{NC}")
    print(f"{BLUE}{'='*60}{NC}")


def print_success(text: str):
    print(f"{GREEN}✓{NC} {text}")


def print_error(text: str):
    print(f"{RED}✗{NC} {text}")


def print_warning(text: str):
    print(f"{YELLOW}⚠{NC} {text}")


def print_info(text: str):
    print(f"{BLUE}ℹ{NC} {text}")


def check_python_version() -> bool:
    """Check Python version"""
    print_info("Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 7:
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor} (3.7+ required)")
        return False


def check_python_packages() -> List[Tuple[str, bool]]:
    """Check required Python packages"""
    print_info("Checking required Python packages...")
    
    packages = {
        'aiohttp': 'aiohttp',
        'pymongo': 'pymongo',
        'reportlab': 'reportlab.lib'
    }
    
    results = []
    for display_name, import_name in packages.items():
        try:
            spec = importlib.util.find_spec(import_name)
            if spec is not None:
                print_success(f"{display_name} installed")
                results.append((display_name, True))
            else:
                print_error(f"{display_name} not found")
                results.append((display_name, False))
        except ImportError:
            print_error(f"{display_name} not found")
            results.append((display_name, False))
    
    return results


def check_api_availability() -> bool:
    """Check if backend API is accessible"""
    print_info("Checking backend API...")
    
    api_url = os.getenv("API_BASE_URL", "http://localhost:13457/api")
    health_url = api_url.replace("/api", "") + "/api/health"
    
    try:
        import urllib.request
        import json
        
        req = urllib.request.Request(health_url, method='GET')
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                if data.get('status') == 'ok':
                    print_success(f"Backend API responding at {api_url}")
                    return True
                else:
                    print_warning(f"Backend API responded but status is not 'ok': {data}")
                    return False
            else:
                print_error(f"Backend API returned status {response.status}")
                return False
    except Exception as e:
        print_error(f"Cannot connect to backend API at {api_url}")
        print_info(f"Error: {e}")
        return False


def check_mongodb() -> bool:
    """Check MongoDB connectivity"""
    print_info("Checking MongoDB connection...")
    
    try:
        import pymongo
        
        host = os.getenv("MONGODB_HOST", "localhost")
        port = int(os.getenv("MONGODB_PORT", "27017"))
        
        client = pymongo.MongoClient(host, port, serverSelectionTimeoutMS=5000)
        # Trigger connection
        client.server_info()
        print_success(f"MongoDB accessible at {host}:{port}")
        client.close()
        return True
    except ImportError:
        print_error("pymongo not installed - cannot check MongoDB")
        return False
    except Exception as e:
        print_error(f"Cannot connect to MongoDB")
        print_info(f"Error: {e}")
        return False


def check_file_permissions() -> bool:
    """Check file permissions"""
    print_info("Checking file permissions...")
    
    files_to_check = [
        'stress_test_doc_upload.py',
        'run_stress_test.sh',
        'analyze_stress_test_logs.py'
    ]
    
    all_ok = True
    for filename in files_to_check:
        if os.path.exists(filename):
            if os.access(filename, os.R_OK):
                print_success(f"{filename} is readable")
            else:
                print_error(f"{filename} is not readable")
                all_ok = False
        else:
            print_warning(f"{filename} not found")
    
    return all_ok


def check_upload_volume() -> bool:
    """Check if upload volume is writable"""
    print_info("Checking upload volume...")
    
    # Try to determine upload folder
    upload_folder = os.getenv("UPLOAD_FOLDER", "/app/shared")
    
    if os.path.exists(upload_folder):
        if os.access(upload_folder, os.W_OK):
            print_success(f"Upload folder {upload_folder} is writable")
            return True
        else:
            print_error(f"Upload folder {upload_folder} is not writable")
            return False
    else:
        print_warning(f"Upload folder {upload_folder} does not exist (may be created by backend)")
        return True  # Don't fail - backend might create it


def print_recommendations(issues: List[str]):
    """Print recommendations based on issues found"""
    if not issues:
        return
    
    print_header("RECOMMENDATIONS")
    
    if "python_packages" in issues:
        print_info("Install missing Python packages:")
        print("  pip install -r requirements_stress_test.txt")
    
    if "backend_api" in issues:
        print_info("Start the backend API:")
        print("  cd /home/cloud-user/Projects/unifai/DataPipelineHub/backend")
        print("  python app.py")
    
    if "mongodb" in issues:
        print_info("Start MongoDB:")
        print("  sudo systemctl start mongod")
        print("  # or")
        print("  sudo service mongod start")
    
    if "permissions" in issues:
        print_info("Fix file permissions:")
        print("  chmod +x run_stress_test.sh")
        print("  chmod +x analyze_stress_test_logs.py")


def main():
    """Main verification function"""
    print_header("STRESS TEST SETUP VERIFICATION")
    
    issues = []
    all_checks_passed = True
    
    # Check Python version
    print_header("Python Environment")
    if not check_python_version():
        all_checks_passed = False
        issues.append("python_version")
    
    # Check Python packages
    package_results = check_python_packages()
    if not all(result[1] for result in package_results):
        all_checks_passed = False
        issues.append("python_packages")
    
    # Check services
    print_header("Service Connectivity")
    
    if not check_api_availability():
        all_checks_passed = False
        issues.append("backend_api")
    
    if not check_mongodb():
        all_checks_passed = False
        issues.append("mongodb")
    
    # Check file system
    print_header("File System Checks")
    
    if not check_file_permissions():
        all_checks_passed = False
        issues.append("permissions")
    
    check_upload_volume()  # Warning only
    
    # Print summary
    print_header("VERIFICATION SUMMARY")
    
    if all_checks_passed:
        print_success("All checks passed! Ready to run stress test.")
        print_info("\nTo run the stress test:")
        print("  ./run_stress_test.sh")
        print("  # or")
        print("  python3 stress_test_doc_upload.py")
        return 0
    else:
        print_error("Some checks failed. Please fix the issues above.")
        print_recommendations(issues)
        return 1


if __name__ == "__main__":
    sys.exit(main())

