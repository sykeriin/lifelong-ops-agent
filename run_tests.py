#!/usr/bin/env python3
"""
Comprehensive test suite for Lifelong Ops Agent Benchmark
Run this to verify all components work correctly
"""

import sys

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    try:
        from env.world import WorldState, get_initial_state, advance_week
        from env.memory import PersistentMemory
        from env.tasks import generate_episode, generate_batch
        from env.grader import grade, grade_task_a, grade_task_b, grade_task_c
        from env.kb import search_kb
        from baseline.stateless import StatelessAgent
        from baseline.memory_agent import MemoryAgent
        from eval.lifelong_eval import run_lifelong_eval
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_world_state():
    """Test world state transitions"""
    print("\nTesting world state...")
    try:
        from env.world import get_initial_state, advance_week
        
        s1 = get_initial_state()
        assert s1.week == 1, "Initial week should be 1"
        assert s1.current_policy.refund_window_days == 7, "Week 1 refund window should be 7"
        
        s2 = advance_week(s1)
        assert s2.week == 2, "Week 2 should be 2"
        assert s2.current_policy.refund_window_days == 30, "Week 2 refund window should be 30"
        
        s3 = advance_week(s2)
        assert s3.week == 3, "Week 3 should be 3"
        assert s3.current_policy.refund_window_days == 14, "Week 3 refund window should be 14"
        
        # Check Pro plan pricing
        assert s1.plans["Pro"].monthly_price == 29.0, "Week 1 Pro should be $29"
        assert s2.plans["Pro"].monthly_price == 29.0, "Week 2 Pro should still be $29"
        assert s3.plans["Pro"].monthly_price == 39.0, "Week 3 Pro should be $39"
        
        print("✓ World state transitions correct")
        return True
    except Exception as e:
        print(f"✗ World state test failed: {e}")
        return False

def test_memory():
    """Test persistent memory"""
    print("\nTesting memory...")
    try:
        from env.memory import PersistentMemory
        
        mem = PersistentMemory()
        assert len(mem.keys()) == 0, "Memory should start empty"
        
        mem.write("test_key", "test_value")
        assert mem.read("test_key") == "test_value", "Should read what was written"
        assert "test_key" in mem.keys(), "Key should be in keys list"
        
        mem.write("test_key", "new_value")
        assert mem.read("test_key") == "new_value", "Should overwrite"
        
        assert mem.read("nonexistent") is None, "Should return None for missing key"
        
        snapshot = mem.snapshot()
        assert snapshot["test_key"] == "new_value", "Snapshot should contain data"
        
        mem.reset()
        assert len(mem.keys()) == 0, "Reset should clear memory"
        
        print("✓ Memory operations correct")
        return True
    except Exception as e:
        print(f"✗ Memory test failed: {e}")
        return False

def test_kb():
    """Test knowledge base search"""
    print("\nTesting knowledge base...")
    try:
        from env.kb import search_kb
        from env.world import get_initial_state, advance_week
        
        s1 = get_initial_state()
        results = search_kb("refund policy", s1, top_k=3)
        assert len(results) > 0, "Should find refund policy articles"
        assert any("refund" in r["title"].lower() for r in results), "Results should mention refund"
        
        # Check that only valid articles are returned
        for article in results:
            assert article["valid_from_week"] <= s1.week, "Article should be valid"
            if article["valid_until_week"] is not None:
                assert article["valid_until_week"] >= s1.week, "Article should not be expired"
        
        print("✓ Knowledge base search correct")
        return True
    except Exception as e:
        print(f"✗ KB test failed: {e}")
        return False

def test_tasks():
    """Test ticket generation"""
    print("\nTesting ticket generation...")
    try:
        from env.tasks import generate_episode, generate_batch
        from env.world import get_initial_state
        
        state = get_initial_state()
        
        # Test single episode
        ticket_a = generate_episode("A", state, 42)
        assert ticket_a["task_type"] == "A", "Should generate task A"
        assert "ground_truth" in ticket_a, "Should have ground truth"
        assert "category" in ticket_a["ground_truth"], "Task A should have category"
        
        ticket_b = generate_episode("B", state, 43)
        assert ticket_b["task_type"] == "B", "Should generate task B"
        assert "decision" in ticket_b["ground_truth"], "Task B should have decision"
        
        ticket_c = generate_episode("C", state, 44)
        assert ticket_c["task_type"] == "C", "Should generate task C"
        assert "is_legacy" in ticket_c["ground_truth"], "Task C should have is_legacy"
        
        # Test batch generation
        batch = generate_batch("A", state, 10, 42)
        assert len(batch) == 10, "Should generate 10 tickets"
        
        # Test reproducibility (check content, not UUID)
        batch2 = generate_batch("A", state, 10, 42)
        assert batch[0]["subject"] == batch2[0]["subject"], "Same seed should produce same tickets"
        assert batch[0]["customer"]["plan"] == batch2[0]["customer"]["plan"], "Same seed should produce same customer"
        
        print("✓ Ticket generation correct")
        return True
    except Exception as e:
        print(f"✗ Task test failed: {e}")
        return False

def test_graders():
    """Test grading functions"""
    print("\nTesting graders...")
    try:
        from env.grader import (
            TASK_SCORE_MAX,
            TASK_SCORE_MIN,
            grade,
            grade_task_a,
            grade_task_b,
            grade_task_c,
        )
        
        # Test Task A grader
        score_a = grade_task_a("This is a billing issue with high priority", {
            "category": "billing",
            "priority": "high"
        })
        assert score_a == TASK_SCORE_MAX, f"Perfect raw score must clamp to open (0,1), got {score_a}"
        
        # Test Task B grader
        score_b = grade_task_b("I approve this refund within 30-day window", {
            "decision": "approve",
            "key_reason": "within 30-day refund window",
            "correct_policy_version": "v2"
        }, None)
        assert score_b >= 0.8, f"Should score >= 0.8, got {score_b}"
        
        # Test full grade function
        ticket = {
            "task_type": "A",
            "ground_truth": {"category": "refund", "priority": "high"},
            "policy_version_expected": "v1"
        }
        result = grade("This is a refund request with high priority", ticket, None)
        assert result["score"] == TASK_SCORE_MAX, "Perfect raw score clamps to (0,1) open upper bound"
        assert result["correct"] is True, "Should be correct"

        bad = grade("", ticket, None)
        assert bad["score"] == TASK_SCORE_MIN, "Empty answer clamps to open lower bound"
        
        print("✓ Graders correct")
        return True
    except Exception as e:
        print(f"✗ Grader test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("LIFELONG OPS AGENT BENCHMARK - TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_world_state,
        test_memory,
        test_kb,
        test_tasks,
        test_graders
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n✅ All tests passed! System is ready.")
        return 0
    else:
        print("\n❌ Some tests failed. Check output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
