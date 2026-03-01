"""
LLM配置器测试
=============

测试LLM调用、重试机制和错误捕获。
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from modules.llm_configurator import LLMConfigurator


class TestLLMConfigurator:
    """LLM配置器测试"""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI 客户端"""
        with patch('modules.llm_configurator.OpenAI') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client
    
    def test_init_volcengine(self):
        """测试火山方舟初始化"""
        config = {
            'type': 'volcengine',
            'api_key': 'test_key',
            'model': 'doubao-seed-2-0-mini-260215',
            'base_url': 'https://ark.cn-beijing.volces.com/api/v3'
        }
        
        with patch('modules.llm_configurator.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.models.list.return_value = MagicMock()
            
            llm = LLMConfigurator(config)
            
            assert llm.llm_type == 'volcengine'
            assert llm.model == 'doubao-seed-2-0-mini-260215'
    
    def test_init_openai(self):
        """测试OpenAI初始化"""
        config = {
            'type': 'openai',
            'api_key': 'test_key',
            'model': 'gpt-4o'
        }
        
        with patch('modules.llm_configurator.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.models.list.return_value = MagicMock()
            
            llm = LLMConfigurator(config)
            
            assert llm.llm_type == 'openai'
            assert llm.model == 'gpt-4o'
    
    def test_invalid_llm_type(self):
        """测试无效的LLM类型"""
        config = {
            'type': 'invalid_type',
            'api_key': 'test_key',
            'model': 'test_model'
        }
        
        with pytest.raises(ValueError, match="不支持的LLM类型"):
            LLMConfigurator(config)


class TestLLMRetryMechanism:
    """LLM重试机制测试"""
    
    def test_retry_on_failure(self):
        """测试失败重试"""
        config = {
            'type': 'volcengine',
            'api_key': 'test_key',
            'model': 'doubao-seed-2-0-mini-260215'
        }
        
        call_count = 0
        
        def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return MagicMock(
                choices=[MagicMock(message=MagicMock(content='{"key": "value"}'))]
            )
        
        with patch('modules.llm_configurator.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create = mock_create
            mock_openai.return_value = mock_client
            
            llm = LLMConfigurator(config)
            
            # 第三次调用应该成功
            result = llm.call_json("test prompt")
            assert result == {"key": "value"}
            assert call_count == 3


class TestLLMErrorHandling:
    """LLM错误处理测试"""
    
    def test_json_parse_error(self):
        """测试JSON解析错误"""
        config = {
            'type': 'volcengine',
            'api_key': 'test_key',
            'model': 'doubao-seed-2-0-mini-260215'
        }
        
        with patch('modules.llm_configurator.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content='invalid json'))]
            )
            mock_openai.return_value = mock_client
            
            llm = LLMConfigurator(config)
            
            with pytest.raises(ValueError, match="非有效JSON"):
                llm.call_json("test prompt")
    
    def test_api_error(self):
        """测试API错误"""
        config = {
            'type': 'volcengine',
            'api_key': 'test_key',
            'model': 'doubao-seed-2-0-mini-260215'
        }
        
        with patch('modules.llm_configurator.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("API Error: 429")
            mock_openai.return_value = mock_client
            
            llm = LLMConfigurator(config)
            
            # 重试3次后应抛出异常
            with pytest.raises(RuntimeError, match="API调用失败"):
                llm.call_json("test prompt")


class TestCallText:
    """文本调用测试"""
    
    def test_call_text(self):
        """测试文本调用"""
        config = {
            'type': 'volcengine',
            'api_key': 'test_key',
            'model': 'doubao-seed-2-0-mini-260215'
        }
        
        with patch('modules.llm_configurator.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content='Hello World'))]
            )
            mock_openai.return_value = mock_client
            
            llm = LLMConfigurator(config)
            
            result = llm.call_text("test prompt")
            assert result == "Hello World"
