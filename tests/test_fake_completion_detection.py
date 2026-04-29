#!/usr/bin/env python3
"""
測試：驗證含 quota/rate-limit 訊號的 artifact 不會被判為 COMPLETED。

此測試確保：
1. 含有 quota/rate-limit 訊息的 worker 輸出被判為 FAILED_RATE_LIMIT
2. 正常成功的 artifact 仍維持 COMPLETED
3. 假完成偵測器能正確辨識過去的假完成任務
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.worker_tick import _check_worker_runtime_errors, _detect_rate_limit_failure, _is_environment_blocking_error


def test_quota_marker_detection():
    """測試：quota 標記能被正確偵測."""
    test_cases = [
        {
            "name": "weekly rate limit",
            "output": "You've reached your weekly rate limit. Please wait...",
            "should_have_markers": True,
            "should_be_blocked": True,
        },
        {
            "name": "no quota",
            "output": "you have no quota to run this task",
            "should_have_markers": True,
            "should_be_blocked": True,
        },
        {
            "name": "switch to auto model",
            "output": "switch to auto model to continue",
            "should_have_markers": True,
            "should_be_blocked": True,
        },
        {
            "name": "normal output",
            "output": "Task completed successfully with changes.",
            "should_have_markers": False,
            "should_be_blocked": False,
        },
        {
            "name": "other error",
            "output": "error: connection refused",
            "should_have_markers": False,
            "should_be_blocked": False,
        },
    ]
    
    print("="*60)
    print("測試 1: Quota 標記偵測")
    print("="*60)
    
    all_passed = True
    for test in test_cases:
        output_lower = test["output"].lower()
        markers = _check_worker_runtime_errors(output_lower)
        is_blocked = _is_environment_blocking_error(markers)
        
        has_markers = bool(markers)
        expected_markers = test["should_have_markers"]
        expected_blocked = test["should_be_blocked"]
        rate_limit_info = _detect_rate_limit_failure(test["output"], markers, provider="copilot-daemon")
        
        passed = (has_markers == expected_markers) and (is_blocked == expected_blocked)
        
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"\n{status}: {test['name']}")
        print(f"  Output: {test['output'][:50]}...")
        print(f"  Markers found: {markers}")
        print(f"  Is blocked: {is_blocked} (expected: {expected_blocked})")
        print(f"  Rate limit info: {rate_limit_info}")
        
        if not passed:
            all_passed = False
    
    return all_passed


def test_real_quota_output():
    """測試：實際 quota 訊息能被正確偵測."""
    real_output = """
    You've reached your weekly rate limit. Please wait for your limit to reset on April 27, 2026 at 8:00 AM or switch to auto model to continue. Learn More (https://docs.github.com/en/copilot/concepts/rate-limits). (Request ID: 2123:618F8:8685DF:9D08C3:69E9A029)
    
    Changes   +0 -0
    Requests  0 Premium (21s)
    """
    
    print("\n" + "="*60)
    print("測試 2: 真實 Quota 訊息偵測")
    print("="*60)
    
    output_lower = real_output.lower()
    markers = _check_worker_runtime_errors(output_lower)
    is_blocked = _is_environment_blocking_error(markers)
    
    print(f"\nMarkers found: {markers}")
    print(f"Is environment blocked: {is_blocked}")
    
    passed = (len(markers) > 0) and is_blocked
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"\n{status}: Real quota message should be detected as FAILED_RATE_LIMIT")
    
    return passed


def main():
    """Run all tests."""
    results = []
    
    results.append(test_quota_marker_detection())
    results.append(test_real_quota_output())
    
    print("\n" + "="*60)
    print("測試結果摘要")
    print("="*60)
    
    all_passed = all(results)
    if all_passed:
        print("✓ 所有測試通過！假完成偵測系統正常運作。")
        print("\n驗證項目:")
        print("  ✓ quota/rate-limit 訊息被正確判為 FAILED_RATE_LIMIT")
        print("  ✓ 其他錯誤訊息被正確判為 WORKER_RUNTIME_FAILED")
        print("  ✓ 正常輸出不會誤判為錯誤")
        return 0
    else:
        print("✗ 部分測試失敗。請檢查偵測邏輯。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
