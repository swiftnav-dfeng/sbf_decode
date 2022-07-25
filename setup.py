from setuptools import setup, find_packages


setup(
    name="sbf_decode",
    version="0.0.2",
    author="Swift Operations",
    author_email="operations@swift-nav.com",
    description="Decode Septentrio Binary Format",
    packages=find_packages(where='sbf_decode'),
    package_dir={"": "sbf_decode"},
    install_requires=[
        'goldcrest-devices',
        'crc',
        'requests',
    ],
)