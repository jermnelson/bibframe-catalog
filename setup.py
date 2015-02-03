from setuptools import find_packages, setup
import os

here = os.path.abspath(os.path.dirname(__file__))
version_file = open(os.path.join(here, "VERSION"))

setup(
    name = 'bibframe_catalog',
    version=version_file.read().strip(),
    description='BIBFRAME Search and Access Catalog',
    url='https://github.com/jermnelson/bibframe-catalog',
    author='Jeremy Nelson',
    author_email='jermnelson@gmail.com',
    license='GPLv3',
    classifiers=[
        'License :: OSI Approved :: GPLv3',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    keywords='bibframe catalog fedora elastic search',
    packages = find_packages(),
    include_package_data=True,
    platforms='any',
    install_requires=[
        'Flask',
        'Flask-Negotiate',
        'pymarc',
        'Flask-FedoraCommons',
        'elasticsearch',
        'rdflib']
)




