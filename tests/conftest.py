def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: Tests that hit external services. "
        "Run with `pytest -m integration`.",
    )
