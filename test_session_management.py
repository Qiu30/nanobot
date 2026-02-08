"""Test script for session management functionality."""

import time
from nanobot.bridge.claude_code import ClaudeCodeBridge


def test_session_management():
    """Test session management features."""
    print("=" * 60)
    print("Testing Session Management Functionality")
    print("=" * 60)

    bridge = ClaudeCodeBridge()

    # Test 1: Set and get session
    print("\n[Test 1] Set and get session")
    context_key = "feishu:chat_123"
    session_id = "sess-abc-123"

    bridge.set_session_id(context_key, session_id)
    retrieved_session = bridge.get_session_id(context_key)

    assert retrieved_session == session_id, f"Expected {session_id}, got {retrieved_session}"
    print(f"✓ Set session: {context_key} -> {session_id}")
    print(f"✓ Retrieved session: {retrieved_session}")

    # Test 2: Get non-existent session
    print("\n[Test 2] Get non-existent session")
    non_existent = bridge.get_session_id("feishu:chat_999")
    assert non_existent is None, f"Expected None, got {non_existent}"
    print(f"✓ Non-existent session returns None")

    # Test 3: Update existing session
    print("\n[Test 3] Update existing session")
    new_session_id = "sess-xyz-456"
    bridge.set_session_id(context_key, new_session_id)
    updated_session = bridge.get_session_id(context_key)

    assert updated_session == new_session_id, f"Expected {new_session_id}, got {updated_session}"
    print(f"✓ Updated session: {context_key} -> {new_session_id}")

    # Test 4: Multiple contexts
    print("\n[Test 4] Multiple contexts")
    context_key_2 = "feishu:chat_456"
    session_id_2 = "sess-def-789"

    bridge.set_session_id(context_key_2, session_id_2)

    session_1 = bridge.get_session_id(context_key)
    session_2 = bridge.get_session_id(context_key_2)

    assert session_1 == new_session_id, f"Context 1: Expected {new_session_id}, got {session_1}"
    assert session_2 == session_id_2, f"Context 2: Expected {session_id_2}, got {session_2}"
    print(f"✓ Context 1: {context_key} -> {session_1}")
    print(f"✓ Context 2: {context_key_2} -> {session_2}")

    # Test 5: Clear session
    print("\n[Test 5] Clear session")
    cleared = bridge.clear_session(context_key)
    assert cleared is True, "Expected True for clearing existing session"

    cleared_session = bridge.get_session_id(context_key)
    assert cleared_session is None, f"Expected None after clear, got {cleared_session}"
    print(f"✓ Cleared session for {context_key}")

    # Test 6: Clear non-existent session
    print("\n[Test 6] Clear non-existent session")
    cleared = bridge.clear_session("feishu:chat_999")
    assert cleared is False, "Expected False for clearing non-existent session"
    print(f"✓ Clearing non-existent session returns False")

    # Test 7: Session expiry (simulated)
    print("\n[Test 7] Session expiry")
    # Set a session with a very short expiry time for testing
    original_expiry = bridge.SESSION_EXPIRY_SECONDS
    bridge.SESSION_EXPIRY_SECONDS = 2  # 2 seconds for testing

    context_key_3 = "feishu:chat_789"
    session_id_3 = "sess-ghi-012"
    bridge.set_session_id(context_key_3, session_id_3)

    # Immediately retrieve - should work
    session = bridge.get_session_id(context_key_3)
    assert session == session_id_3, f"Expected {session_id_3}, got {session}"
    print(f"✓ Session retrieved immediately: {session}")

    # Wait for expiry
    print("  Waiting 3 seconds for session to expire...")
    time.sleep(3)

    # Try to retrieve expired session
    expired_session = bridge.get_session_id(context_key_3)
    assert expired_session is None, f"Expected None for expired session, got {expired_session}"
    print(f"✓ Expired session returns None")

    # Restore original expiry time
    bridge.SESSION_EXPIRY_SECONDS = original_expiry

    # Test 8: Cleanup expired sessions
    print("\n[Test 8] Cleanup expired sessions")
    bridge.SESSION_EXPIRY_SECONDS = 2

    # Create multiple sessions
    for i in range(3):
        bridge.set_session_id(f"feishu:chat_{i}", f"sess-{i}")

    print(f"  Created 3 sessions")
    print(f"  Current sessions: {len(bridge._sessions)}")

    # Wait for expiry
    time.sleep(3)

    # Cleanup
    bridge.cleanup_expired_sessions()
    print(f"  After cleanup: {len(bridge._sessions)} sessions")
    assert len(bridge._sessions) == 0, f"Expected 0 sessions after cleanup, got {len(bridge._sessions)}"
    print(f"✓ All expired sessions cleaned up")

    # Restore original expiry time
    bridge.SESSION_EXPIRY_SECONDS = original_expiry

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)


if __name__ == "__main__":
    test_session_management()
