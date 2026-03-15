import pytest
from app.memory.session import init_redis, get_redis, clear_history


@pytest.fixture(scope="session", autouse=True)
async def redis_connection():
    """Inicializa o Redis uma vez para todos os testes."""
    await init_redis()
    yield


@pytest.fixture(autouse=True)
async def cleanup_redis():
    """Limpa dados de teste no Redis após cada teste."""
    yield
    r = get_redis()
    # Remove chaves de leads e histórico de teste
    test_keys = await r.keys("lead:5511*")
    test_keys += await r.keys("history:5511*")
    if test_keys:
        await r.delete(*test_keys)
