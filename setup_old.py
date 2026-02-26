"""Setup configuration for ERPNext Migration Toolkit."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip() 
        for line in requirements_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="erpnext-migration-toolkit",
    version="0.1.0",
    author="Tbw",
    description="Generic ERPNext migration toolkit with Jupyter notebooks",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tbwaiyaki/erpnext-migration-toolkit",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=requirements,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Office/Business :: Financial",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="erpnext migration accounting jupyter",
    project_urls={
        "Documentation": "https://github.com/yourusername/erpnext-migration-toolkit/docs",
        "Source": "https://github.com/yourusername/erpnext-migration-toolkit",
        "Tracker": "https://github.com/yourusername/erpnext-migration-toolkit/issues",
    },
)
