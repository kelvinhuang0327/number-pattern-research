import requests
import time
import json
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8002"

def wait_for_server(url, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            resp = requests.get(f"{url}/api/ping", timeout=2)
            if resp.status_code == 200:
                logger.info("Server is up!")
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
        logger.info("Waiting for server...")
    return False

def test_health():
    try:
        resp = requests.get(f"{BASE_URL}/health")
        if resp.status_code == 200:
            logger.info("✅ Health Check Passed")
            return True
        else:
            logger.error(f"❌ Health Check Failed: {resp.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Health Check Error: {e}")
        return False

def test_list_models():
    try:
        resp = requests.get(f"{BASE_URL}/api/models?lottery_type=BIG_LOTTO")
        if resp.status_code == 200:
            data = resp.json()
            if "models" in data and len(data["models"]) > 0:
                logger.info(f"✅ List Models Passed (Found {len(data['models'])} models)")
                return True
            else:
                logger.error("❌ List Models Failed: No models returned")
                return False
        else:
            logger.error(f"❌ List Models Failed: {resp.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ List Models Error: {e}")
        return False

def test_csv_validation():
    try:
        csv_content = "Date,Draw,1,2,3,4,5,6,Special\n2023/01/01,112000001,1,2,3,4,5,6,7"
        files = {'file': ('test.csv', csv_content, 'text/csv')}
        data = {'lottery_type': 'BIG_LOTTO'}
        
        resp = requests.post(f"{BASE_URL}/api/data/validate-csv", files=files, data=data)
        
        if resp.status_code == 200:
            res_json = resp.json()
            if res_json.get("valid") is True:
                logger.info("✅ CSV Validation (Valid Case) Passed")
            else:
                logger.error(f"❌ CSV Validation (Valid Case) Failed: {res_json}")
                return False
                
        # Test Invalid
        csv_invalid = "Date,Draw,1,2,3,4,5,6,Special\nInvalidDate,112000001,1,2,3,4,5,6,7"
        files['file'] = ('invalid.csv', csv_invalid, 'text/csv')
        resp = requests.post(f"{BASE_URL}/api/data/validate-csv", files=files, data=data)
        if resp.status_code == 200:
            res_json = resp.json()
            if res_json.get("valid") is False:
                 logger.info("✅ CSV Validation (Invalid Case) Passed")
            else:
                 logger.error("❌ CSV Validation (Invalid Case) Failed: Should be invalid")
                 return False
        
        return True
    except Exception as e:
        logger.error(f"❌ CSV Validation Error: {e}")
        return False

def main():
    if not wait_for_server(BASE_URL):
        logger.error("Server failed to start")
        sys.exit(1)
        
    results = []
    results.append(test_health())
    results.append(test_list_models())
    results.append(test_csv_validation())
    
    if all(results):
        logger.info("🎉 All Tests Passed!")
        sys.exit(0)
    else:
        logger.error("Some tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
