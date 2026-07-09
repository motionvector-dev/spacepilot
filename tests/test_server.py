import os
import sys

# Add project root to sys.path to find the src module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force mock video mode for testing to prevent model downloads
os.environ["MOCK_VIDEO"] = "true"

from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)

def test_health_check():
    """Verify health check endpoint returns correct system status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mock_mode"] is True

def test_enhance_prompt():
    """Verify prompt enhancement API with fallback rule engine."""
    response = client.post("/enhance", json={"prompt": "cyberpunk street"})
    assert response.status_code == 200
    data = response.json()
    assert "enhanced_prompt" in data
    assert len(data["enhanced_prompt"]) > len("cyberpunk street")

def test_generate_video_mock():
    """Verify mock video generation returns video/mp4 output."""
    response = client.post(
        "/generate",
        json={
            "prompt": "cyberpunk street",
            "width": 256,
            "height": 256,
            "num_frames": 9,
            "steps": 5
        }
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"

if __name__ == "__main__":
    print("Running API integration tests locally...")
    try:
        test_health_check()
        print("✓ Health check endpoint test passed")
        test_enhance_prompt()
        print("✓ Enhance prompt endpoint test passed")
        test_generate_video_mock()
        print("✓ Generate video endpoint test passed")
        print("\nAll integration tests passed successfully!")
    except Exception as err:
        print(f"\nTest failed with error: {err}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

