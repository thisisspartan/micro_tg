from setuptools import setup, find_packages

setup(
    name="tmdb",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "redis",
        "requests",
        "python-json-logger",
        "python-dotenv"
    ],
)
