from setuptools import find_packages
from setuptools import setup

setup(
    name='erc_nav_benchmark',
    version='1.0.0',
    packages=find_packages(
        include=('erc_nav_benchmark', 'erc_nav_benchmark.*')),
)
