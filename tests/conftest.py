import pytest
import app.memory.session as session_store
from app.memory.session import init_redis, get_redis


@pytest.fixture(autouse=True)
async def redis_connection():
    """Inicializa o Redis por teste, limpa dados e encerra conexão no teardown."""
    await init_redis()
    yield
    r = get_redis()
    test_keys = await r.keys("lead:5511*")
    test_keys += await r.keys("history:5511*")
    test_keys += await r.keys("script_lock:5511*")
    test_keys += await r.keys("msg_seen:*")
    if test_keys:
        await r.delete(*test_keys)
    await r.aclose()
    session_store._redis = None
