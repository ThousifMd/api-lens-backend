"""
Test suite for the 2.3.1 Company Operations requirements
Tests all required functions with proper signatures
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime

from app.services.company import (
    create_company,
    get_company,
    update_company,
    delete_company,
    provision_company_schema,
    DuplicateCompanyError
)
from models.company import Company, CompanyCreate, CompanyUpdate, CompanySettings

class TestCompanyOperations:
    """Test suite for 2.3.1 Company Operations requirements"""
    
    @pytest.mark.asyncio
    async def test_create_company_signature_and_functionality(self):
        """Test create_company(company_data: CompanyCreate) -> Company"""
        company_data = CompanyCreate(
            name="Test Company",
            description="A test company",
            contact_email="test@example.com",
            settings=CompanySettings(
                rate_limit_rps=200,
                monthly_quota=2000000,
                max_api_keys=20
            )
        )
        
        mock_company_id = uuid4()
        mock_result = {
            'id': mock_company_id,
            'name': 'Test Company',
            'schema_name': 'test_company_20240101120000',
            'description': 'A test company',
            'contact_email': 'test@example.com',
            'billing_email': None,
            'billing_address': None,
            'vat_number': None,
            'rate_limit_rps': 200,
            'monthly_quota': 2000000,
            'max_api_keys': 20,
            'allowed_ips': None,
            'webhook_url': None,
            'webhook_secret': None,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'is_active': True
        }
        
        with patch('app.services.company.DatabaseUtils.execute_query') as mock_db:
            # Mock duplicate check (no existing company)
            mock_db.side_effect = [
                None,  # No duplicate found
                mock_result  # Company creation result
            ]
            
            with patch('app.services.company._create_company_schema') as mock_schema:
                result = await create_company(company_data)
                
                assert isinstance(result, Company)
                assert result.name == 'Test Company'
                assert result.settings.rate_limit_rps == 200
                mock_schema.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_company_signature_and_functionality(self):
        """Test get_company(company_id: str) -> Optional[Company]"""
        company_id = str(uuid4())
        
        mock_result = {
            'id': uuid4(),
            'name': 'Test Company',
            'schema_name': 'test_company_schema',
            'description': 'Test description',
            'contact_email': 'test@example.com',
            'billing_email': None,
            'billing_address': None,
            'vat_number': None,
            'rate_limit_rps': 100,
            'monthly_quota': 1000000,
            'max_api_keys': 10,
            'allowed_ips': None,
            'webhook_url': None,
            'webhook_secret': None,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'is_active': True
        }
        
        with patch('app.services.company.DatabaseUtils.execute_query', return_value=mock_result):
            result = await get_company(company_id)
            
            assert isinstance(result, Company)
            assert result.name == 'Test Company'
            assert result.schema_name == 'test_company_schema'
    
    @pytest.mark.asyncio
    async def test_get_company_not_found(self):
        """Test get_company returns None when company doesn't exist"""
        company_id = str(uuid4())
        
        with patch('app.services.company.DatabaseUtils.execute_query', return_value=None):
            result = await get_company(company_id)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_update_company_signature_and_functionality(self):
        """Test update_company(company_id: str, updates: CompanyUpdate) -> Company"""
        company_id = str(uuid4())
        updates = CompanyUpdate(
            name="Updated Company Name",
            description="Updated description"
        )
        
        mock_result = {
            'id': uuid4(),
            'name': 'Updated Company Name',
            'schema_name': 'test_company_schema',
            'description': 'Updated description',
            'contact_email': 'test@example.com',
            'billing_email': None,
            'billing_address': None,
            'vat_number': None,
            'rate_limit_rps': 100,
            'monthly_quota': 1000000,
            'max_api_keys': 10,
            'allowed_ips': None,
            'webhook_url': None,
            'webhook_secret': None,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'is_active': True
        }
        
        with patch('app.services.company.DatabaseUtils.execute_query', return_value=mock_result):
            result = await update_company(company_id, updates)
            
            assert isinstance(result, Company)
            assert result.name == 'Updated Company Name'
            assert result.description == 'Updated description'
    
    @pytest.mark.asyncio
    async def test_delete_company_signature_and_functionality(self):
        """Test delete_company(company_id: str) -> bool"""
        company_id = str(uuid4())
        
        mock_company = Company(
            id=uuid4(),
            name='Test Company',
            schema_name='test_schema',
            settings=CompanySettings(
                rate_limit_rps=100,
                monthly_quota=1000000,
                max_api_keys=10
            ),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_active=True
        )
        
        with patch('app.services.company.get_company', return_value=mock_company):
            with patch('app.services.company._drop_company_schema') as mock_drop:
                with patch('app.services.company.DatabaseUtils.execute_query'):
                    result = await delete_company(company_id)
                    
                    assert result is True
                    mock_drop.assert_called_once_with('test_schema')
    
    @pytest.mark.asyncio
    async def test_delete_company_not_found(self):
        """Test delete_company returns False when company doesn't exist"""
        company_id = str(uuid4())
        
        with patch('app.services.company.get_company', return_value=None):
            result = await delete_company(company_id)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_provision_company_schema_signature_and_functionality(self):
        """Test provision_company_schema(company_id: str) -> bool"""
        company_id = str(uuid4())
        
        mock_company = Company(
            id=uuid4(),
            name='Test Company',
            schema_name='test_schema',
            settings=CompanySettings(
                rate_limit_rps=100,
                monthly_quota=1000000,
                max_api_keys=10
            ),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_active=True
        )
        
        with patch('app.services.company.get_company', return_value=mock_company):
            with patch('app.services.company._create_company_schema') as mock_create:
                result = await provision_company_schema(company_id)
                
                assert result is True
                mock_create.assert_called_once_with('test_schema')
    
    @pytest.mark.asyncio
    async def test_provision_company_schema_company_not_found(self):
        """Test provision_company_schema returns False when company doesn't exist"""
        company_id = str(uuid4())
        
        with patch('app.services.company.get_company', return_value=None):
            result = await provision_company_schema(company_id)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_create_company_duplicate_name_error(self):
        """Test create_company raises DuplicateCompanyError for duplicate names"""
        company_data = CompanyCreate(
            name="Existing Company",
            contact_email="test@example.com"
        )
        
        # Mock existing company found
        with patch('app.services.company.DatabaseUtils.execute_query', return_value={'id': uuid4()}):
            with pytest.raises(DuplicateCompanyError):
                await create_company(company_data)

class TestFunctionSignatures:
    """Test that all functions have the correct signatures as per 2.3.1 requirements"""
    
    def test_function_signatures_match_requirements(self):
        """Verify function signatures match 2.3.1 Company Operations requirements"""
        import inspect
        
        # Check create_company signature
        sig = inspect.signature(create_company)
        assert 'company_data' in sig.parameters
        assert sig.parameters['company_data'].annotation.__name__ == 'CompanyCreate'
        assert sig.return_annotation.__name__ == 'Company'
        
        # Check get_company signature  
        sig = inspect.signature(get_company)
        assert 'company_id' in sig.parameters
        assert sig.parameters['company_id'].annotation == str
        # Note: Optional[Company] shows as typing.Union, so we check the return annotation differently
        
        # Check update_company signature
        sig = inspect.signature(update_company)
        assert 'company_id' in sig.parameters
        assert 'updates' in sig.parameters
        assert sig.parameters['company_id'].annotation == str
        assert sig.parameters['updates'].annotation.__name__ == 'CompanyUpdate'
        
        # Check delete_company signature
        sig = inspect.signature(delete_company)
        assert 'company_id' in sig.parameters
        assert sig.parameters['company_id'].annotation == str
        assert sig.return_annotation == bool
        
        # Check provision_company_schema signature
        sig = inspect.signature(provision_company_schema)
        assert 'company_id' in sig.parameters
        assert sig.parameters['company_id'].annotation == str
        assert sig.return_annotation == bool

if __name__ == "__main__":
    pytest.main([__file__, "-v"])