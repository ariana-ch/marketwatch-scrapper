#!/usr/bin/env python3
"""
Setup script for marketwatch package.
"""

from setuptools import setup, find_packages

if __name__ == "__main__":
    setup(
        name="marketwatch",
        version="0.1.0",
        description="A Python package for scraping MarketWatch articles from the Wayback Machine",
        author="Ariana Christodoulou",
        author_email="ariana.chr@gmail.com",
        url="https://github.com/ariana-ch/marketwatch-scrapper",
        packages=find_packages(where="src"),
        package_dir={"": "src"},
        include_package_data=True,
    ) 