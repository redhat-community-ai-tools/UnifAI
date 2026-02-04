"""RAG Service Package Setup."""
from setuptools import setup, find_packages

# Read dependencies from requirements.txt
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="rag",
    version="1.0.0",
    packages=find_packages(exclude=["tests", "tests.*", "venv", "venv.*"]),
    install_requires=requirements,
    python_requires=">=3.11",
)

