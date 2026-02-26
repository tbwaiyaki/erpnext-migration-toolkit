"""Setup configuration for ERPNext Migration Toolkit."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Define dependencies directly (not from requirements.txt)
# Git dependencies must go in dependency_links, not install_requires
install_requires = [
    "pandas>=2.0.0,<3.0.0",
    "numpy>=1.24.0,<2.0.0",
    "pydantic>=2.0.0,<3.0.0",
    "python-dateutil>=2.8.0",
    "pyyaml>=6.0",
    "ipython>=8.0.0",
    "ipywidgets>=8.0.0",
    "tqdm>=4.65.0",
    "loguru>=0.7.0",
    "requests>=2.31.0",
]

# Git dependencies are handled separately
dependency_links = [
    "git+https://github.com/frappe/frappe-client.git@master#egg=frappe-client",
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
    install_requires=install_requires,
    dependency_links=dependency_links,
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
        "Documentation": "https://github.com/tbwaiyaki/erpnext-migration-toolkit/docs",
        "Source": "https://github.com/tbwaiyaki/erpnext-migration-toolkit",
        "Tracker": "https://github.com/tbwaiyaki/erpnext-migration-toolkit/issues",
    },
)
