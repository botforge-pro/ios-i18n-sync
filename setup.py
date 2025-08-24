from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ios-i18n-sync",
    version="0.1.0",
    author="botforge.pro",
    description="iOS localization sync tool for .strings files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/botforge-pro/ios-i18n-sync",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Internationalization",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "PyYAML>=6.0",
        "click>=8.0",
    ],
    entry_points={
        "console_scripts": [
            "i18n-sync=i18n_sync.cli:main",
        ],
    },
)