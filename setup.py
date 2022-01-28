from pathlib import Path

from setuptools import find_packages, setup

import warehub

here = Path(__file__).parent.resolve()

long_description = (here / 'README.md').read_text(encoding='utf-8')

base_url = 'https://github.com/Mimer29or40/warehub'

setup(
    name=warehub.__name__,
    version=warehub.__version__,
    description=warehub.__description__,
    long_description=long_description,
    long_description_content_type='text/markdown',
    author=warehub.__author__,
    author_email=warehub.__author_email__,
    maintainer=warehub.__maintainer__,
    maintainer_email=warehub.__maintainer_email__,
    url=base_url,
    download_url='https://pypi.org/project/warehub/',
    project_urls={
        'Source Code':   base_url,
        'Documentation': base_url + '/wiki',
        'Bug Tracker':   base_url + '/issues',
    },
    packages=find_packages(where='src'),
    classifiers=[
        # 'Development Status :: 1 - Planning',
        # 'Development Status :: 2 - Pre-Alpha',
        # 'Development Status :: 3 - Alpha',
        'Development Status :: 4 - Beta',
        # 'Development Status :: 5 - Production/Stable',
        # 'Development Status :: 6 - Mature',
        # 'Development Status :: 7 - Inactive',
        'Environment :: Console',
        'Environment :: Other Environment',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Database',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Version Control :: Git',
        'Topic :: Utilities',
    ],
    keywords=[
        'pypi',
        'warehouse',
        'twine',
        'warehub',
        'github',
        'actions',
    ],
    package_dir={'': 'src'},
    
    python_requires='>=3.8',
    install_requires=[
        'docopt',
    ],
    extras_require={
        'dev':    [
            'setuptools',
            'wheel',
            'tox',
            'build',
        ],
        'upload': [
            'twine',
        ],
    },
)
