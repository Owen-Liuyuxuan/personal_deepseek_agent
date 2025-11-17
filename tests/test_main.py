"""
Tests for main.py functionality.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import sys


class TestMain:
    """Test main.py functions."""
    
    def test_send_to_feishu_success(self):
        """Test successful Feishu message sending."""
        from main import send_to_feishu
        
        with patch('main.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"code": 0}
            mock_post.return_value = mock_response
            
            result = send_to_feishu(
                webhook_url="https://test.url",
                title="Test",
                timestamp="2024-01-01 00:00:00",
                text="Test message"
            )
            
            assert result is True
            mock_post.assert_called_once()
    
    def test_send_to_feishu_failure(self):
        """Test failed Feishu message sending."""
        from main import send_to_feishu
        
        with patch('main.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"code": 1, "msg": "Error"}
            mock_post.return_value = mock_response
            
            result = send_to_feishu(
                webhook_url="https://test.url",
                title="Test",
                timestamp="2024-01-01 00:00:00",
                text="Test message"
            )
            
            assert result is False
    
    def test_send_to_feishu_no_url(self):
        """Test Feishu sending with no URL."""
        from main import send_to_feishu
        
        result = send_to_feishu(
            webhook_url="",
            title="Test",
            timestamp="2024-01-01 00:00:00",
            text="Test message"
        )
        
        assert result is False

