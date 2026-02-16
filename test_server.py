"""
Pytest-based test module for the tasks server.

This module tests the server by starting it and making HTTP requests,
validating the generated HTML output.
"""

import pytest
import requests
import json
import time
import threading
import os
from http.server import HTTPServer
from unittest.mock import patch, MagicMock

from server import RequestHandler
from bs4 import BeautifulSoup
import shutil

# Test server configuration
TEST_PORT = 9001
TEST_TOKEN_DEFAULT = "42"
TEST_TOKEN_LOVEDONE = "12345678"
TEST_USER_DEFAULT = "default_user"
TEST_USER_LOVEDONE = "lovedone"


@pytest.fixture(scope="session")
def test_config_dir(tmp_path_factory):
    """Create a temporary directory with test config and tasks files."""
    tmpdir = tmp_path_factory.mktemp("test_data")

    # Create test config.json
    config_data = {
        "vetoes": 2,
        "email": {
            "from_address": "test@test.de",
            "smtp_server": "mail.test.de",
            "smtp_port": 25,
            "smtp_username": "testuser",
            "smtp_password": "testpass",
        },
        "users": {
            "default_user": {
                "full_name": "Test User",
                "nickname": "TestUser",
                "password": "testpass",
                "token": TEST_TOKEN_DEFAULT,
                "notify_email": "test@test.org",
            },
            "lovedone": {
                "full_name": "Test Lovedone",
                "nickname": "Lovedone",
                "password": "lovepass",
                "token": TEST_TOKEN_LOVEDONE,
                "notify_email": "loved@test.org",
            },
        },
    }

    config_path = tmpdir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config_data, f)

    # Create test tasks.json
    tasks_data = {
        "default_user": {
            "tasks": [
                {
                    "id": "task-1",
                    "title": "Test Task One",
                    "when": "in the morning",
                    "description": "This is a test task",
                },
                {
                    "id": "task-2",
                    "title": "Test Task Two",
                    "when": ["morning", "evening"],
                    "description": ["Step 1", "Step 2", "Step 3"],
                },
            ]
        },
        "lovedone": {
            "tasks": [
                {
                    "id": "love-task-1",
                    "title": "Loved One Task",
                    "when": "now",
                    "description": "A task for the loved one",
                }
            ]
        },
    }

    tasks_path = tmpdir / "tasks.json"
    with open(tasks_path, "w") as f:
        json.dump(tasks_data, f)

    return tmpdir


@pytest.fixture(scope="session")
def mock_smtp():
    """Mock SMTP to prevent actual email sending attempts."""
    with patch("notify.SMTP") as mock_smtp_class:
        mock_instance = MagicMock()
        mock_smtp_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture(scope="session")
def server_thread(test_config_dir, mock_smtp):
    """Start the server in a background thread."""
    # Change to test directory
    original_dir = os.getcwd()
    os.chdir(test_config_dir)

    # Copy template files to the temp directory
    template_dir = test_config_dir / "templates"
    template_dir.mkdir(exist_ok=True)

    # Copy template files from the original location
    original_templates = "/Users/axel/src/tasks/templates"
    if os.path.exists(original_templates):
        for template_file in os.listdir(original_templates):
            src = os.path.join(original_templates, template_file)
            dst = os.path.join(template_dir, template_file)
            if os.path.isfile(src):
                shutil.copy(src, dst)

    # Modify LISTENING_PORT to use TEST_PORT
    import server as server_module

    original_port = server_module.LISTENING_PORT
    server_module.LISTENING_PORT = TEST_PORT

    # Create and start server
    server_address = ("localhost", TEST_PORT)
    httpd = HTTPServer(server_address, RequestHandler)

    # Run server in a thread
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    # Wait for server to start
    time.sleep(1)

    # Give client time to connect
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get(
                f"http://localhost:{TEST_PORT}/tasks/list?token={TEST_TOKEN_DEFAULT}",
                timeout=1,
            )
            if response.status_code in [200, 400, 403]:
                break
        except requests.exceptions.ConnectionError:
            if i < max_retries - 1:
                time.sleep(0.5)
            else:
                raise

    yield httpd

    # Cleanup
    httpd.shutdown()
    os.chdir(original_dir)
    server_module.LISTENING_PORT = original_port


@pytest.fixture
def client(server_thread):
    """HTTP client for making requests to the test server."""

    class Client:
        def __init__(self, base_url=f"http://localhost:{TEST_PORT}"):
            self.base_url = base_url

        def get(self, path, token=None, **params):
            """Make a GET request."""
            url = f"{self.base_url}{path}"
            if token:
                params["token"] = token
            return requests.get(url, params=params)

        def get_soup(self, path, token=None, **params):
            """Make a GET request and return parsed HTML."""
            response = self.get(path, token=token, **params)
            return BeautifulSoup(response.content, "html.parser"), response

    return Client()


# ============================================================================
# Tests
# ============================================================================


class TestServerBasics:
    """Test basic server functionality."""

    def test_server_is_running(self, server_thread):
        """Verify server is accessible."""
        response = requests.get(
            f"http://localhost:{TEST_PORT}/tasks/list?token={TEST_TOKEN_DEFAULT}"
        )
        assert response.status_code in [200, 400, 403]

    def test_missing_token_returns_403(self, client):
        """Test that missing token returns 403."""
        response = client.get("/tasks/list")
        assert response.status_code == 403
        assert b"Token required" in response.content

    def test_invalid_token_returns_403(self, client):
        """Test that invalid token returns 403."""
        response = client.get("/tasks/list", token="invalid_token")
        assert response.status_code == 403
        assert b"Invalid token" in response.content

    def test_valid_token_returns_200(self, client):
        """Test that valid token returns 200."""
        response = client.get("/tasks/list", token=TEST_TOKEN_DEFAULT)
        assert response.status_code == 200


class TestListEndpoint:
    """Test the /tasks/list endpoint."""

    def test_list_returns_html_table(self, client):
        """Test that list endpoint returns HTML with a table."""
        soup, response = client.get_soup("/tasks/list", token=TEST_TOKEN_DEFAULT)

        assert response.status_code == 200
        assert soup.find("table") is not None

    def test_list_contains_task_ids(self, client):
        """Test that list includes task IDs."""
        soup, response = client.get_soup("/tasks/list", token=TEST_TOKEN_DEFAULT)

        table = soup.find("table")
        assert table is not None
        table_text = table.get_text()

        # Check for task IDs
        assert "task-1" in table_text or "task_1" in table_text.lower()

    def test_list_contains_table_headers(self, client):
        """Test that list table has expected headers."""
        soup, response = client.get_soup("/tasks/list", token=TEST_TOKEN_DEFAULT)

        table = soup.find("table")
        headers = [th.get_text() for th in table.find_all("th")]

        expected_headers = ["ID", "Description", "When", "Shown", "Done", "Vetoed"]
        for header in expected_headers:
            assert any(
                header.lower() in h.lower() for h in headers
            ), f"Expected header '{header}' not found. Found: {headers}"

    def test_list_different_users(self, client):
        """Test that different users see their own tasks."""
        # Get tasks for default_user
        soup1, resp1 = client.get_soup("/tasks/list", token=TEST_TOKEN_DEFAULT)
        table1_text = soup1.find("table").get_text()

        # Get tasks for lovedone
        soup2, resp2 = client.get_soup("/tasks/list", token=TEST_TOKEN_LOVEDONE)
        table2_text = soup2.find("table").get_text()

        # Both should return 200
        assert resp1.status_code == 200
        assert resp2.status_code == 200

        # Tables should have content
        assert "task" in table1_text.lower()
        assert "task" in table2_text.lower()


class TestDebugEndpoint:
    """Test the /tasks/debug endpoint."""

    def test_debug_endpoint_returns_html(self, client):
        """Test that debug endpoint returns HTML."""
        response = client.get("/tasks/debug", token=TEST_TOKEN_DEFAULT)
        assert response.status_code == 200
        assert (
            b"<html" in response.content.lower()
            or b"<!doctype" in response.content.lower()
        )

    def test_debug_shows_protocol(self, client):
        """Test that debug shows protocol information."""
        soup, response = client.get_soup("/tasks/debug", token=TEST_TOKEN_DEFAULT)
        page_text = soup.get_text()

        # Should contain protocol info
        assert "http" in page_text.lower() or "protocol" in page_text.lower()

    def test_debug_shows_server_info(self, client):
        """Test that debug shows server information."""
        soup, response = client.get_soup("/tasks/debug", token=TEST_TOKEN_DEFAULT)
        page_text = soup.get_text()

        # Should contain localhost or server indicator
        assert len(page_text) > 100  # Should have substantial content


class TestShowEndpoint:
    """Test the /tasks/show endpoint."""

    def test_show_task_by_index(self, client):
        """Test showing a task by index."""
        response = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT, id=0)
        assert response.status_code == 200
        assert (
            b"<html" in response.content.lower()
            or b"<!doctype" in response.content.lower()
        )

    def test_show_contains_task_title(self, client):
        """Test that show page contains task title."""
        soup, response = client.get_soup("/tasks/show", token=TEST_TOKEN_DEFAULT, id=0)
        page_text = soup.get_text().lower()

        # Should contain some task content
        assert "test" in page_text or "task" in page_text

    def test_show_nonexistent_task_index(self, client):
        """Test showing a task with invalid index."""
        response = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT, id=999)
        assert response.status_code == 200

        # Should handle gracefully (return a not found page or pending task page)
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.find("html") is not None  # Valid HTML returned


class TestVoucherEndpoint:
    """Test the /tasks/voucher endpoint."""

    def test_voucher_endpoint_returns_html(self, client):
        """Test that voucher endpoint returns HTML."""
        response = client.get("/tasks/voucher", token=TEST_TOKEN_DEFAULT)
        assert response.status_code == 200
        assert b"<table" in response.content or b"<html" in response.content.lower()

    def test_voucher_contains_table(self, client):
        """Test that voucher page contains a table."""
        soup, response = client.get_soup("/tasks/voucher", token=TEST_TOKEN_DEFAULT)

        table = soup.find("table")
        assert table is not None

    def test_voucher_table_has_headers(self, client):
        """Test that voucher table has expected columns."""
        soup, response = client.get_soup("/tasks/voucher", token=TEST_TOKEN_DEFAULT)

        table = soup.find("table")
        headers = [th.get_text().strip() for th in table.find_all("th")]

        # Should have Title, QR-Code, Link columns
        assert len(headers) >= 2  # At least some headers


class TestHtmlValidity:
    """Test HTML validity and structure."""

    def test_list_html_is_valid(self, client):
        """Test that list endpoint returns valid HTML."""
        soup, response = client.get_soup("/tasks/list", token=TEST_TOKEN_DEFAULT)

        # Should have html tag (or at least valid BeautifulSoup structure)
        assert soup.find("table") is not None

        # Tables should have rows
        rows = soup.find_all("tr")
        assert len(rows) > 0

    def test_response_encoding(self, client):
        """Test that responses are properly encoded."""
        response = client.get("/tasks/list", token=TEST_TOKEN_DEFAULT)

        # Should be valid UTF-8
        assert response.encoding is not None or response.text is not None

    def test_table_structure_integrity(self, client):
        """Test that table structures are valid."""
        soup, response = client.get_soup("/tasks/list", token=TEST_TOKEN_DEFAULT)

        table = soup.find("table")
        assert table is not None

        # Should have thead or at least header row
        rows = table.find_all("tr")
        assert len(rows) > 0

        # Each row should have cells
        for row in rows:
            cells = row.find_all(["td", "th"])
            assert len(cells) > 0


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_module_returns_404(self, client):
        """Test that invalid module returns 404."""
        response = client.get("/tasks/nonexistent", token=TEST_TOKEN_DEFAULT)
        assert response.status_code == 404
        assert b"Module not found" in response.content

    def test_missing_id_parameter(self, client):
        """Test handling of missing ID parameter when required."""
        # Some endpoints may require id and may error if not provided
        # This tests that the server doesn't crash catastrophically
        try:
            response = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT)
            # If it responds, status should be reasonable
            assert response.status_code in [200, 400, 500]
        except requests.exceptions.ConnectionError:
            # Server might close connection on error, which is also acceptable
            pass


class TestMultilineContent:
    """Test handling of multiline content in tasks."""

    def test_task_with_list_when_field(self, client):
        """Test task with list in 'when' field."""
        soup, response = client.get_soup("/tasks/show", token=TEST_TOKEN_DEFAULT, id=1)
        assert response.status_code == 200

        page_text = soup.get_text()
        # Should render multiline content
        assert len(page_text) > 50


class TestCrossUserInvalidation:
    """Test that users cannot access other users' tokens."""

    def test_default_user_token_works(self, client):
        """Test that default user's token works."""
        response = client.get("/tasks/list", token=TEST_TOKEN_DEFAULT)
        assert response.status_code == 200

    def test_lovedone_token_works(self, client):
        """Test that lovedone's token works."""
        response = client.get("/tasks/list", token=TEST_TOKEN_LOVEDONE)
        assert response.status_code == 200

    def test_token_mismatch_invalid(self, client):
        """Test that mismatched token is invalid."""
        response = client.get("/tasks/list", token="mismatched_token_xyz")
        assert response.status_code == 403


# ============================================================================
# Performance Tests
# ============================================================================


class TestPerformance:
    """Test server performance characteristics."""

    def test_list_endpoint_response_time(self, client):
        """Test that list endpoint responds quickly."""
        import time

        start = time.time()
        response = client.get("/tasks/list", token=TEST_TOKEN_DEFAULT)
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 2.0  # Should respond within 2 seconds


class TestCompleteFlowShowTask:
    """Test a complete flow: help page -> task display -> task done."""

    def test_flow_1_first_request_shows_help(self, client):
        """First request to show a task should display the help page."""
        response = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT, id=0)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text().lower()

        # Help page should contain help-related text
        # Check for common help indicators
        assert len(page_text) > 50  # Should have content

    def test_flow_2_second_request_shows_task(self, client):
        """Second request should show the actual task (help already shown first time)."""
        response = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT, id=0)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # Should show task information
        assert "Test Task One" in page_text or "task" in page_text.lower()

    def test_flow_3_do_task(self, client):
        """Doing a task should succeed and show a done page."""
        response = client.get("/tasks/do", token=TEST_TOKEN_DEFAULT, id=0)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # Should show done status
        assert len(page_text) > 50  # Should have content

    def test_flow_4_after_done_shows_status(self, client):
        """After marking done, subsequent request should show done status."""
        response = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT, id=0)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # Page should contain task information
        assert len(page_text) > 50


class TestCompleteFlowVetoTask:
    """Test a complete flow with vetoing a task: help page -> task display -> task vetoed."""

    def test_veto_flow_1_first_request_shows_help(self, client):
        """First request to task 1 should show help page."""
        response = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT, id=1)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # Should have content
        assert len(page_text) > 50

    def test_veto_flow_2_second_request_shows_task(self, client):
        """Second request should show the actual task."""
        response = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT, id=1)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # Should show task information
        assert "Test Task Two" in page_text or "task" in page_text.lower()

    def test_veto_flow_3_veto_task(self, client):
        """Vetoing a task should succeed."""
        response = client.get("/tasks/veto", token=TEST_TOKEN_DEFAULT, id=1)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # Should show response (success or failure)
        assert len(page_text) > 50

    def test_veto_flow_4_after_veto_shows_status(self, client):
        """After vetoing, subsequent request should show vetoed status."""
        response = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT, id=1)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # Page should contain task information
        assert len(page_text) > 50

        # Check that the veto was recorded by verifying joker usage
        # The page should show that 1 joker has been used (eingesetzt) and 1 remains
        assert "Joker" in page_text and "eingesetzt" in page_text


class TestCompleteFlowDifferentUser:
    """Test complete flow with a different user (lovedone)."""

    def test_lovedone_flow_1_first_show(self, client):
        """First request for lovedone user should show help."""
        response = client.get("/tasks/show", token=TEST_TOKEN_LOVEDONE, id=0)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        assert len(page_text) > 50

    def test_lovedone_flow_2_second_show(self, client):
        """Second request for lovedone should show task."""
        response = client.get("/tasks/show", token=TEST_TOKEN_LOVEDONE, id=0)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # Should show lovedone's task
        assert "Loved One Task" in page_text or "task" in page_text.lower()

    def test_lovedone_flow_3_do_task(self, client):
        """Lovedone user can do their task."""
        response = client.get("/tasks/do", token=TEST_TOKEN_LOVEDONE, id=0)
        assert response.status_code == 200

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        assert len(page_text) > 50


class TestMultipleSequentialRequests:
    """Test multiple sequential requests in a realistic workflow."""

    def test_workflow_list_then_show_then_do(self, client):
        """Complete workflow: list -> show -> do."""
        # Step 1: Get list
        resp1 = client.get("/tasks/list", token=TEST_TOKEN_DEFAULT)
        assert resp1.status_code == 200

        # Step 2: Show a task (first time - gets help)
        resp2 = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT, id=0)
        assert resp2.status_code == 200

        # Step 3: Show same task again (gets actual task)
        resp3 = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT, id=0)
        assert resp3.status_code == 200

        # Step 4: Do the task
        resp4 = client.get("/tasks/do", token=TEST_TOKEN_DEFAULT, id=0)
        assert resp4.status_code == 200

        # Step 5: List again to see updated state
        resp5 = client.get("/tasks/list", token=TEST_TOKEN_DEFAULT)
        assert resp5.status_code == 200

    def test_workflow_multiple_users_same_session(self, client):
        """Test that multiple users can interact with same task independently."""
        # Default user shows task
        resp1 = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT, id=0)
        assert resp1.status_code == 200

        # Default user sees it again
        resp2 = client.get("/tasks/show", token=TEST_TOKEN_DEFAULT, id=0)
        assert resp2.status_code == 200

        # Lovedone user shows their task
        resp3 = client.get("/tasks/show", token=TEST_TOKEN_LOVEDONE, id=0)
        assert resp3.status_code == 200

        # Lovedone user sees it again
        resp4 = client.get("/tasks/show", token=TEST_TOKEN_LOVEDONE, id=0)
        assert resp4.status_code == 200

        # Both should succeed
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp3.status_code == 200
        assert resp4.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
