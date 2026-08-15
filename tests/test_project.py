import importlib.metadata


def test_project_version():
    version = importlib.metadata.version("angelone-mf-portfolio")
    assert version == "0.1.0"
    