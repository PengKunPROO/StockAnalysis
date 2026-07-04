def test_cleanup_function_exists():
    from app.engine.scheduler import cleanup_old_data
    assert callable(cleanup_old_data)


def test_sync_function_exists():
    from app.engine.scheduler import sync_all_daily_klines
    assert callable(sync_all_daily_klines)
