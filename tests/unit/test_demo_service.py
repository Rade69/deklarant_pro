# tests/unit/test_demo_service.py

"""
Unit Testovi za DemoService

Testiraju business logiku izolovano od GUI-a.
"""

import pytest
from services.demo_service import DemoService
from services.base_service import ValidationError


class TestDemoServiceValidation:
    """Testovi za validaciju."""
    
    @pytest.fixture
    def service(self):
        """Kreiraj service za testove."""
        return DemoService()
    
    def test_validation_valid_data(self, service):
        """Test da validni podaci prolaze validaciju."""
        data = {
            'name': 'John Doe',
            'email': 'john@example.com',
        }
        
        result = service.validate(data)
        
        assert result is True
    
    def test_validation_empty_name(self, service):
        """Test da prazan name baca ValidationError."""
        data = {
            'name': '',
            'email': 'john@example.com',
        }
        
        with pytest.raises(ValidationError) as exc_info:
            service.validate(data)
        
        assert "Name je obavezan" in str(exc_info.value)
        assert exc_info.value.field == 'name'
    
    def test_validation_missing_name(self, service):
        """Test da nedostajući name baca ValidationError."""
        data = {
            'email': 'john@example.com',
        }
        
        with pytest.raises(ValidationError) as exc_info:
            service.validate(data)
        
        assert "Name je obavezan" in str(exc_info.value)
    
    def test_validation_empty_email(self, service):
        """Test da prazan email baca ValidationError."""
        data = {
            'name': 'John',
            'email': '',
        }
        
        with pytest.raises(ValidationError) as exc_info:
            service.validate(data)
        
        assert "Email je obavezan" in str(exc_info.value)
        assert exc_info.value.field == 'email'
    
    def test_validation_email_without_at(self, service):
        """Test da email bez @ baca ValidationError."""
        data = {
            'name': 'John',
            'email': 'johnexample.com',
        }
        
        with pytest.raises(ValidationError) as exc_info:
            service.validate(data)
        
        assert "mora sadržavati @" in str(exc_info.value)
        assert exc_info.value.field == 'email'


class TestDemoServiceSave:
    """Testovi za save operaciju."""
    
    @pytest.fixture
    def service(self):
        """Kreiraj service za testove."""
        return DemoService()
    
    def test_save_valid_data(self, service):
        """Test čuvanja validnih podataka."""
        data = {
            'name': 'John Doe',
            'email': 'john@example.com',
        }
        
        result = service.save_data(data)
        
        assert result is True
    
    def test_save_invalid_data(self, service):
        """Test da čuvanje nevalidnih podataka baca ValidationError."""
        data = {
            'name': '',
            'email': 'invalid',
        }
        
        with pytest.raises(ValidationError):
            service.save_data(data)
    
    def test_save_logs_operation(self, service, caplog):
        """Test da save operacija loguje."""
        import logging
        with caplog.at_level(logging.INFO):
            data = {'name': 'John', 'email': 'john@example.com'}
            service.save_data(data)
        
        assert "Saving data" in caplog.text
        assert "saved successfully" in caplog.text


class TestDemoServiceGetAll:
    """Testovi za get_all_data."""
    
    @pytest.fixture
    def service(self):
        """Kreiraj service za testove."""
        return DemoService()
    
    def test_get_all_returns_list(self, service):
        """Test da get_all_data vraća listu."""
        result = service.get_all_data()
        
        assert isinstance(result, list)
    
    def test_get_all_empty_by_default(self, service):
        """Test da je lista prazna po defaultu."""
        result = service.get_all_data()
        
        assert len(result) == 0
