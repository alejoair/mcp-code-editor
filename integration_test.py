#!/usr/bin/env python3
"""
Test script to verify integration of features between fixes and master branches.

This script tests:
1. Console tools with intelligent input detection
2. Static analysis and dependency detection
3. Library context integration
"""

def test_function_with_breaking_change(new_param_only):
    """This function will be modified to test breaking change detection."""
    return old_param + new_param

def helper_function():
    """Helper function to test dependency analysis."""
    return test_function_with_breaking_change("hello", "world")

if __name__ == "__main__":
    print("Testing integrated features...")
    result = helper_function()
    print(f"Result: {result}")
