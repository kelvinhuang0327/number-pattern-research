#!/usr/bin/env python3
"""
Concurrent Request Test Script
Tests that the backend can handle concurrent requests without blocking.
"""

import asyncio
import aiohttp
import time
from datetime import datetime

API_BASE = "http://localhost:5001"

async def test_health_check(session, test_id):
    """Test health check endpoint"""
    start = time.time()
    try:
        async with session.get(f"{API_BASE}/health") as response:
            elapsed = time.time() - start
            status = response.status
            data = await response.json()
            print(f"[{test_id}] Health check: {status} in {elapsed:.2f}s")
            return {"test_id": test_id, "status": status, "elapsed": elapsed, "success": True}
    except Exception as e:
        elapsed = time.time() - start
        print(f"[{test_id}] Health check FAILED: {e} after {elapsed:.2f}s")
        return {"test_id": test_id, "status": 0, "elapsed": elapsed, "success": False, "error": str(e)}

async def test_heavy_prediction(session, test_id):
    """Test a CPU-intensive prediction (Monte Carlo)"""
    start = time.time()
    
    # Sample data for testing
    payload = {
        "lotteryType": "大樂透",
        "modelType": "monte_carlo"
    }
    
    try:
        async with session.post(f"{API_BASE}/api/predict-from-backend", json=payload) as response:
            elapsed = time.time() - start
            status = response.status
            if status == 200:
                data = await response.json()
                print(f"[{test_id}] Prediction: {status} in {elapsed:.2f}s - Numbers: {data.get('numbers', [])}")
            else:
                text = await response.text()
                print(f"[{test_id}] Prediction: {status} in {elapsed:.2f}s - Error: {text[:100]}")
            return {"test_id": test_id, "status": status, "elapsed": elapsed, "success": status == 200}
    except Exception as e:
        elapsed = time.time() - start
        print(f"[{test_id}] Prediction FAILED: {e} after {elapsed:.2f}s")
        return {"test_id": test_id, "status": 0, "elapsed": elapsed, "success": False, "error": str(e)}

async def test_concurrent_blocking():
    """
    Test that a heavy prediction doesn't block health checks.
    
    Before fix: Health checks will hang until prediction completes.
    After fix: Health checks should return immediately.
    """
    print("\n" + "="*60)
    print("TEST: Concurrent Request Non-Blocking")
    print("="*60)
    print("Starting a heavy prediction and immediately checking health...")
    print()
    
    async with aiohttp.ClientSession() as session:
        # Start a heavy prediction
        prediction_task = asyncio.create_task(test_heavy_prediction(session, "PREDICTION"))
        
        # Wait a tiny bit to ensure prediction starts
        await asyncio.sleep(0.1)
        
        # Fire 3 health checks while prediction is running
        health_tasks = [
            asyncio.create_task(test_health_check(session, f"HEALTH-{i}"))
            for i in range(1, 4)
        ]
        
        # Wait for all tasks
        all_results = await asyncio.gather(prediction_task, *health_tasks)
        
        print("\n" + "-"*60)
        print("RESULTS:")
        print("-"*60)
        
        health_results = [r for r in all_results if r['test_id'].startswith('HEALTH')]
        prediction_result = [r for r in all_results if r['test_id'] == 'PREDICTION'][0]
        
        # Check if health checks were fast
        max_health_time = max(r['elapsed'] for r in health_results)
        
        print(f"\nPrediction time: {prediction_result['elapsed']:.2f}s")
        print(f"Max health check time: {max_health_time:.2f}s")
        
        if max_health_time < 1.0:
            print("\n✅ PASS: Health checks responded quickly (< 1s)")
            print("   Backend is NOT blocking on heavy computations!")
        else:
            print("\n❌ FAIL: Health checks were slow (>= 1s)")
            print("   Backend may still be blocking on heavy computations.")
        
        return max_health_time < 1.0

async def test_multiple_predictions():
    """Test multiple predictions running concurrently"""
    print("\n" + "="*60)
    print("TEST: Multiple Concurrent Predictions")
    print("="*60)
    print("Starting 3 predictions simultaneously...")
    print()
    
    async with aiohttp.ClientSession() as session:
        tasks = [
            asyncio.create_task(test_heavy_prediction(session, f"PRED-{i}"))
            for i in range(1, 4)
        ]
        
        results = await asyncio.gather(*tasks)
        
        print("\n" + "-"*60)
        print("RESULTS:")
        print("-"*60)
        
        successful = sum(1 for r in results if r['success'])
        avg_time = sum(r['elapsed'] for r in results) / len(results)
        
        print(f"\nSuccessful: {successful}/3")
        print(f"Average time: {avg_time:.2f}s")
        
        if successful == 3:
            print("\n✅ PASS: All predictions completed successfully")
        else:
            print(f"\n⚠️  WARNING: Only {successful}/3 predictions succeeded")
        
        return successful == 3

async def main():
    print("\n" + "="*60)
    print("CONNECTION STABILITY TEST SUITE")
    print("="*60)
    print(f"Testing backend at: {API_BASE}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if backend is running
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}/health") as response:
                if response.status == 200:
                    print("✅ Backend is running")
                else:
                    print(f"⚠️  Backend returned status {response.status}")
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("\nPlease start the backend first:")
        print("  cd lottery-api && ./start.sh")
        return
    
    # Run tests
    test1_pass = await test_concurrent_blocking()
    await asyncio.sleep(1)  # Brief pause between tests
    test2_pass = await test_multiple_predictions()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Concurrent Non-Blocking: {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print(f"Multiple Predictions:    {'✅ PASS' if test2_pass else '❌ FAIL'}")
    
    if test1_pass and test2_pass:
        print("\n🎉 All tests passed! Connection stability is good.")
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
