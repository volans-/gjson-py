#!/usr/bin/env python
"""Package configuration."""
from setuptools import find_packages, setup


with open('README.rst', 'r') as readme:
    long_description = readme.read()

# Extra dependencies
extras_require = {
    # Test dependencies
    'tests': [
        'bandit',
        'flake8',
        'flake8-import-order',
        'mypy',
        'pytest-cov',
        'pytest-xdist',
        'pytest',
        'sphinx_rtd_theme',
        'sphinx-argparse',
        'sphinx-autodoc-typehints',
        'Sphinx',
        'types-pkg_resources',
    ],
    'prospector': [
        'prospector[with_everything]',
        'pytest',
    ],
}

setup_requires = [
    'pytest-runner',
    'setuptools_scm',
]

setup(
    author='Riccardo Coccioli',
    author_email='volans-@users.noreply.github.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
    ],
    description=('gjson-py is a Python package that provides a simple way to filter and extract data from JSON-like '
                 'objects or JSON files, using the GJSON syntax.'),
    entry_points={
        'console_scripts': [
            'gjson = gjson:cli',
        ],
    },
    extras_require=extras_require,
    install_requires=[],
    keywords=['gjson'],
    license='GPLv3+',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    name='gjson',
    packages=find_packages(),
    platforms=['GNU/Linux', 'BSD', 'MacOSX'],
    setup_requires=setup_requires,
    url='https://github.com/volans-/gjson-py',
    use_scm_version=True,
    zip_safe=False,
)
