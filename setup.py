# setup.py
#
# Standard Python packaging file. Frappe apps are just Python packages that
# follow the framework's folder conventions -- `bench get-app` essentially just
# git-clones the repo and pip-installs it via this file, then `bench install-app`
# registers it against a specific site's database.

from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

setup(
	name="asset_maintenance",
	version="0.0.1",
	description="Custom Frappe/ERPNext app for tracking asset maintenance requests",
	author="Kinzang Dorji",
	author_email="kinzasdorji66@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires,
)
