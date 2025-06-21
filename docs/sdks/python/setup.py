"""
API Lens Python SDK Setup Configuration
"""

from setuptools import setup, find_packages
import os

# Read version from package
def get_version():
    """Get version from package __init__.py"""
    version_file = os.path.join(os.path.dirname(__file__), 'apilens', '__init__.py')
    with open(version_file, 'r') as f:
        for line in f:
            if line.startswith('__version__'):
                return line.split('=')[1].strip().strip('"\'')
    return '1.0.0'

# Read README for long description
def get_long_description():
    """Get long description from README"""
    readme_file = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_file):
        with open(readme_file, 'r', encoding='utf-8') as f:
            return f.read()
    return "API Lens Python SDK - AI API cost tracking and analytics"

# Read requirements
def get_requirements():
    """Get requirements from requirements.txt"""
    requirements_file = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(requirements_file):
        with open(requirements_file, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return [
        'httpx>=0.24.0',
        'pydantic>=2.0.0',
        'python-dateutil>=2.8.0',
        'typing-extensions>=4.0.0',
    ]

setup(
    name="apilens-python",
    version=get_version(),
    author="API Lens Team",
    author_email="support@apilens.dev",
    description="Official Python client library for API Lens - AI API cost tracking and analytics",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/apilens/python-sdk",
    project_urls={
        "Documentation": "https://docs.apilens.dev/python",
        "Homepage": "https://apilens.dev",
        "Repository": "https://github.com/apilens/python-sdk",
        "Bug Tracker": "https://github.com/apilens/python-sdk/issues",
        "Changelog": "https://github.com/apilens/python-sdk/blob/main/CHANGELOG.md",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: System :: Monitoring",
        "Typing :: Typed",
    ],
    python_requires=">=3.8",
    install_requires=get_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
        ],
        "docs": [
            "mkdocs>=1.4.0",
            "mkdocs-material>=9.0.0",
            "mkdocstrings[python]>=0.20.0",
        ],
        "examples": [
            "jupyter>=1.0.0",
            "matplotlib>=3.5.0",
            "pandas>=1.5.0",
            "plotly>=5.0.0",
            "streamlit>=1.20.0",
            "flask>=2.0.0",
            "django>=4.0.0",
        ],
        "all": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
            "mkdocs>=1.4.0",
            "mkdocs-material>=9.0.0",
            "mkdocstrings[python]>=0.20.0",
            "jupyter>=1.0.0",
            "matplotlib>=3.5.0",
            "pandas>=1.5.0",
            "plotly>=5.0.0",
            "streamlit>=1.20.0",
            "flask>=2.0.0",
            "django>=4.0.0",
        ],
    },
    include_package_data=True,
    package_data={
        "apilens": ["py.typed"],
    },
    keywords=[
        "ai", "openai", "anthropic", "google", "api", "cost", "tracking", 
        "analytics", "monitoring", "llm", "gpt", "claude", "gemini",
        "machine-learning", "artificial-intelligence", "usage-tracking"
    ],
    entry_points={
        "console_scripts": [
            "apilens=apilens.cli:main",
        ],
    },
    zip_safe=False,
)