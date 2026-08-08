from setuptools import find_packages, setup

setup(
    name="real-estate-monitor",
    version="0.2.0",
    packages=find_packages(include=["src", "src.*", "config"]),
    install_requires=[
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "sqlalchemy>=2.0.0",
        "streamlit>=1.28.0",
        "plotly>=5.17.0",
        "scikit-learn>=1.3.0",
        "scipy>=1.11.0",
        "python-dotenv>=1.0.0",
        "loguru>=0.7.0",
        "click>=8.1.0",
    ],
    python_requires=">=3.9",
)
