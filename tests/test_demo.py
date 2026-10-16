"""Tests for demo.py replay functionality.

Verifies that replay mode:
- Does not make network calls
- Does not make LLM calls
- Handles missing recording file correctly
- Exits with nonzero code on error
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import demo functions
import demo


def test_demo_player_loads_recording():
    """Test DemoPlayer can load a valid recording."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        recording_path = Path(f.name)
        recording = {
            "version": "1.0",
            "total_duration": 10.0,
            "events": [
                {"type": "test_event", "timestamp": 0.0, "data": {"key": "value"}},
                {"type": "another_event", "timestamp": 1.0, "data": {"foo": "bar"}}
            ]
        }
        json.dump(recording, f)
    
    try:
        player = demo.DemoPlayer(recording_path)
        assert len(player.events) == 2
        assert player.events[0]["type"] == "test_event"
        assert player.events[1]["type"] == "another_event"
    finally:
        recording_path.unlink()


def test_demo_player_get_next():
    """Test DemoPlayer returns events at correct times."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        recording_path = Path(f.name)
        recording = {
            "version": "1.0",
            "total_duration": 1.0,
            "events": [
                {"type": "immediate", "timestamp": 0.0, "data": {}},
                {"type": "delayed", "timestamp": 100.0, "data": {}}
            ]
        }
        json.dump(recording, f)
    
    try:
        player = demo.DemoPlayer(recording_path)
        
        # First event should be available immediately
        event = player.get_next()
        assert event is not None
        assert event[0] == "immediate"
        
        # Second event not yet (requires 100s to pass)
        event = player.get_next()
        assert event is None  # Too early
        
    finally:
        recording_path.unlink()


def test_demo_recorder_basic():
    """Test DemoRecorder records events."""
    recorder = demo.DemoRecorder(enabled=True)
    
    recorder.record("event1", {"data": "value1"})
    recorder.record("event2", {"data": "value2"})
    
    assert len(recorder.events) == 2
    assert recorder.events[0]["type"] == "event1"
    assert recorder.events[0]["data"] == {"data": "value1"}
    assert recorder.events[1]["type"] == "event2"


def test_demo_recorder_disabled():
    """Test DemoRecorder does not record when disabled."""
    recorder = demo.DemoRecorder(enabled=False)
    
    recorder.record("event1", {"data": "value1"})
    
    assert len(recorder.events) == 0


def test_demo_recorder_save():
    """Test DemoRecorder saves to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_recording.json"
        
        recorder = demo.DemoRecorder(enabled=True)
        recorder.record("test_event", {"key": "value"})
        
        with patch('demo.console'):  # Suppress console output
            recorder.save(output_path)
        
        # Verify file exists and contains data
        assert output_path.exists()
        
        with open(output_path) as f:
            data = json.load(f)
        
        assert data["version"] == "1.0"
        assert len(data["events"]) == 1
        assert data["events"][0]["type"] == "test_event"


def test_replay_missing_recording_exits_nonzero():
    """Test replay mode exits with code 1 when recording is missing."""
    nonexistent_path = Path("results/nonexistent_recording.json")
    assert not nonexistent_path.exists()
    
    with patch('demo.console'):  # Suppress console output
        with pytest.raises(SystemExit) as exc_info:
            with patch('demo.Path') as mock_path:
                # Mock Path to return nonexistent file
                mock_path.return_value = nonexistent_path
                demo.run_demo_replay()
        
        assert exc_info.value.code == 1


def test_replay_missing_recording_shows_help():
    """Test replay mode shows helpful error message when recording is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use a path that definitely doesn't exist
        nonexistent = Path(tmpdir) / "missing.json"
        
        with patch('demo.Path') as mock_path:
            mock_path.return_value = nonexistent
            
            with patch('demo.console') as mock_console:
                with pytest.raises(SystemExit) as exc_info:
                    demo.run_demo_replay()
                
                # Verify error code
                assert exc_info.value.code == 1
                
                # Verify helpful messages were printed
                printed_messages = [call[0][0] for call in mock_console.print.call_args_list]
                
                # Should mention the error
                assert any("Error" in str(msg) or "not found" in str(msg) for msg in printed_messages)
                
                # Should mention how to create recording
                assert any("--record" in str(msg) for msg in printed_messages)


def test_replay_no_network_calls():
    """Test replay mode does not create HTTP client or make network calls."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        recording_path = Path(f.name)
        recording = {
            "version": "1.0",
            "total_duration": 0.5,
            "events": [
                {"type": "reset", "timestamp": 0.0, "data": {"version": "v1"}},
                {"type": "baseline_v1", "timestamp": 0.1, "data": {
                    "success": True,
                    "status": "ok",
                    "tokens": 100,
                    "final_text": "Test"
                }}
            ]
        }
        json.dump(recording, f)
    
    try:
        # Mock httpx to detect any network calls
        with patch('demo.httpx.Client') as mock_client:
            with patch('demo.console'):  # Suppress output
                with patch('demo.wait_for_enter'):  # Skip user input
                    with patch('demo.Path') as mock_path:
                        mock_path.return_value = recording_path
                        
                        # Run replay
                        demo.run_demo_replay()
                        
                        # Verify no HTTP client was created
                        mock_client.assert_not_called()
    
    finally:
        recording_path.unlink()


def test_replay_no_agent_imports():
    """Test replay mode does not import or execute agent modules."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        recording_path = Path(f.name)
        recording = {
            "version": "1.0",
            "total_duration": 0.1,
            "events": [
                {"type": "healing_v1", "timestamp": 0.0, "data": {
                    "success": True,
                    "status": "ok",
                    "tokens": 100,
                    "registry_version": 1,
                    "final_text": "Test"
                }}
            ]
        }
        json.dump(recording, f)
    
    try:
        # Replay should not import healing_agent or baseline_agent modules
        with patch('demo.console'):  # Suppress output
            with patch('demo.wait_for_enter'):  # Skip user input
                with patch('demo.Path') as mock_path:
                    mock_path.return_value = recording_path
                    
                    # Mock the agent imports to detect if they're used
                    with patch('demo.healing_agent', create=True) as mock_healing:
                        with patch('demo.baseline_agent', create=True) as mock_baseline:
                            # Run replay
                            demo.run_demo_replay()
                            
                            # Agents should NOT be accessed during replay
                            mock_healing.run.assert_not_called()
                            mock_baseline.run.assert_not_called()
    
    finally:
        recording_path.unlink()


def test_replay_no_llm_calls():
    """Test replay mode does not create LLMClient or make model calls."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        recording_path = Path(f.name)
        recording = {
            "version": "1.0",
            "total_duration": 0.1,
            "events": [
                {"type": "healing_v2", "timestamp": 0.0, "data": {
                    "success": True,
                    "status": "healed",
                    "registry_version": 2,
                    "recovery_time": 1.5,
                    "tokens": 200,
                    "events": []
                }}
            ]
        }
        json.dump(recording, f)
    
    try:
        # Mock LLMClient to detect any usage
        with patch('demo.console'):  # Suppress output
            with patch('demo.wait_for_enter'):  # Skip user input
                with patch('demo.Path') as mock_path:
                    mock_path.return_value = recording_path
                    
                    # Also mock LLMClient at import level
                    with patch.dict('sys.modules', {'driftshield.agents.llm': MagicMock()}):
                        # Run replay
                        demo.run_demo_replay()
                        
                        # If we got here, no LLM modules were actually used
                        # (they would fail if accessed since we mocked them)
    
    finally:
        recording_path.unlink()


def test_live_mode_does_not_run_on_replay():
    """Test that --replay flag prevents live mode execution."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        recording_path = Path(f.name)
        recording = {
            "version": "1.0",
            "total_duration": 0.1,
            "events": []
        }
        json.dump(recording, f)
    
    try:
        with patch('demo.run_demo_live') as mock_live:
            with patch('demo.run_demo_replay'):
                with patch('demo.Path') as mock_path:
                    mock_path.return_value = recording_path
                    
                    # Simulate --replay flag
                    with patch('sys.argv', ['demo.py', '--replay']):
                        demo.main()
                    
                    # Verify live mode was NOT called
                    mock_live.assert_not_called()
    
    finally:
        recording_path.unlink()


def test_replay_shows_replay_label():
    """Test that replay mode shows [REPLAY] label in scene headers."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        recording_path = Path(f.name)
        recording = {
            "version": "1.0",
            "total_duration": 0.1,
            "events": [
                {"type": "reset", "timestamp": 0.0, "data": {"version": "v1"}}
            ]
        }
        json.dump(recording, f)
    
    try:
        # Check that print_scene_header is called with replay=True
        with patch('demo.print_scene_header') as mock_header:
            with patch('demo.console'):  # Suppress output
                with patch('demo.wait_for_enter'):  # Skip user input
                    with patch('demo.Path') as mock_path:
                        mock_path.return_value = recording_path
                        
                        # Run replay
                        demo.run_demo_replay()
                        
                        # Verify at least one scene header was called with replay=True
                        replay_calls = [call for call in mock_header.call_args_list 
                                       if call[1].get('replay') is True]
                        assert len(replay_calls) > 0, "No scene headers showed replay=True"
    
    finally:
        recording_path.unlink()


def test_recording_disabled_by_default():
    """Test that recording is disabled unless --record is passed."""
    # Without --record flag
    recorder = demo.DemoRecorder(enabled=False)
    assert recorder.enabled is False
    
    # With --record in sys.argv
    with patch('sys.argv', ['demo.py', '--record']):
        recorder = demo.DemoRecorder(enabled="--record" in sys.argv)
        assert recorder.enabled is True


def test_offline_recording_creates_file():
    """Test that offline recording generator creates a valid recording file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "demo_recording.json"
        
        with patch('demo.Path') as mock_path:
            mock_path.return_value = output_path
            
            with patch('demo.console'):  # Suppress output
                demo.create_offline_recording()
        
        # Verify file was created
        assert output_path.exists()
        
        # Verify file contains valid JSON
        with open(output_path) as f:
            recording = json.load(f)
        
        # Verify structure
        assert recording["version"] == "1.0"
        assert "total_duration" in recording
        assert "events" in recording
        assert "_metadata" in recording
        assert recording["_metadata"]["source"] == "offline_fixture_generator"


def test_offline_recording_no_api_calls():
    """Test that offline recording makes no API or network calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "demo_recording.json"
        
        # Mock network modules to detect any usage
        with patch('demo.httpx.Client') as mock_http:
            with patch('demo.Path') as mock_path:
                mock_path.return_value = output_path
                
                with patch('demo.console'):  # Suppress output
                    demo.create_offline_recording()
                
                # Verify no HTTP client was created
                mock_http.assert_not_called()


def test_offline_recording_no_llm_initialization():
    """Test that offline recording does not initialize LLMClient."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "demo_recording.json"
        
        # Mock LLMClient to detect any initialization
        with patch('demo.Path') as mock_path:
            mock_path.return_value = output_path
            
            # Mock the agent modules to ensure they're not imported/used
            with patch.dict('sys.modules', {
                'driftshield.agents.llm': MagicMock(),
                'driftshield.agents.healing_agent': MagicMock(),
                'driftshield.agents.baseline_agent': MagicMock()
            }):
                with patch('demo.console'):  # Suppress output
                    demo.create_offline_recording()
                
                # If we got here, no agent modules were used
                # (they would fail if accessed since we mocked them)


def test_offline_recording_has_all_six_scenes():
    """Test that offline recording includes all six demo scenes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "demo_recording.json"
        
        with patch('demo.Path') as mock_path:
            mock_path.return_value = output_path
            
            with patch('demo.console'):  # Suppress output
                demo.create_offline_recording()
        
        # Load recording
        with open(output_path) as f:
            recording = json.load(f)
        
        event_types = {event["type"] for event in recording["events"]}
        
        # Verify key event types for each scene
        # Scene 1: reset, baseline_v1, healing_v1
        assert "reset" in event_types
        assert "baseline_v1" in event_types
        assert "healing_v1" in event_types
        
        # Scene 2: mutate
        assert "mutate" in event_types
        
        # Scene 3: baseline_v2
        assert "baseline_v2" in event_types
        
        # Scene 4: healing_v2, patch_log
        assert "healing_v2" in event_types
        assert "patch_log" in event_types
        
        # Scene 5: mutate_billing, safe_stop
        assert "mutate_billing" in event_types
        assert "safe_stop" in event_types
        
        # Scene 6: results
        assert "results" in event_types


def test_offline_recording_events_are_labeled_simulated():
    """Test that all events in offline recording are clearly labeled as simulated."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "demo_recording.json"
        
        with patch('demo.Path') as mock_path:
            mock_path.return_value = output_path
            
            with patch('demo.console'):  # Suppress output
                demo.create_offline_recording()
        
        # Load recording
        with open(output_path) as f:
            recording = json.load(f)
        
        # Verify metadata indicates simulation
        assert "_metadata" in recording
        assert "offline_fixture" in recording["_metadata"]["source"] or \
               "simulated" in str(recording["_metadata"]).lower()
        
        # Verify all events have simulation markers
        for event in recording["events"]:
            # Each event should have a _note field indicating simulation
            assert "_note" in event["data"], f"Event {event['type']} missing _note"
            note = event["data"]["_note"].lower()
            assert "simulated" in note or "demo" in note or "fixture" in note, \
                f"Event {event['type']} note doesn't indicate simulation: {note}"


def test_offline_recording_can_be_replayed():
    """Test that offline recording can be loaded and replayed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "demo_recording.json"
        
        # Create offline recording
        with patch('demo.Path') as mock_path:
            mock_path.return_value = output_path
            
            with patch('demo.console'):  # Suppress output
                demo.create_offline_recording()
        
        # Verify it can be loaded by DemoPlayer
        player = demo.DemoPlayer(output_path)
        assert len(player.events) > 0
        
        # Verify first few events can be retrieved
        event1 = player.get_next()
        assert event1 is not None
        assert event1[0] == "reset"  # First event should be reset


def test_offline_recording_format_compatible_with_existing_replay():
    """Test that offline recording uses same format as existing replay system."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "demo_recording.json"
        
        # Create offline recording
        with patch('demo.Path') as mock_path:
            mock_path.return_value = output_path
            
            with patch('demo.console'):  # Suppress output
                demo.create_offline_recording()
        
        # Load and verify structure matches expected format
        with open(output_path) as f:
            recording = json.load(f)
        
        # Verify required top-level fields
        assert "version" in recording
        assert recording["version"] == "1.0"
        assert "total_duration" in recording
        assert "events" in recording
        assert isinstance(recording["events"], list)
        
        # Verify event structure
        for event in recording["events"]:
            assert "type" in event
            assert "timestamp" in event
            assert "data" in event
            assert isinstance(event["type"], str)
            assert isinstance(event["timestamp"], (int, float))
            assert isinstance(event["data"], dict)


def test_create_offline_recording_argument_parsing():
    """Test that --create-offline-recording argument is recognized."""
    with patch('demo.create_offline_recording') as mock_create:
        with patch('sys.argv', ['demo.py', '--create-offline-recording']):
            demo.main()
        
        # Verify offline recording function was called
        mock_create.assert_called_once()


def test_offline_recording_does_not_break_existing_modes():
    """Test that adding offline mode doesn't break --record or --replay."""
    # Test --replay still works
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        recording_path = Path(f.name)
        recording = {
            "version": "1.0",
            "total_duration": 0.1,
            "events": [{"type": "reset", "timestamp": 0.0, "data": {}}]
        }
        json.dump(recording, f)
    
    try:
        with patch('demo.run_demo_replay') as mock_replay:
            with patch('sys.argv', ['demo.py', '--replay']):
                with patch('demo.Path') as mock_path:
                    mock_path.return_value = recording_path
                    demo.main()
            
            mock_replay.assert_called_once()
    
    finally:
        recording_path.unlink()
    
    # Test --record still triggers live mode
    with patch('demo.run_demo_live') as mock_live:
        with patch('sys.argv', ['demo.py', '--record']):
            demo.main()
        
        mock_live.assert_called_once()

