from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in services_company/__init__.py
from services_company import __version__ as version

setup(
	name="services_company",
	version=version,
	description="Custom app dedicated to service companies that supports creating a service invoice, submitting a purchase record, a sale record, and the profit percentage in the same doctype",
	author="alaalsalam",
	author_email="alaalsalam101@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
