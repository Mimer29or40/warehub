from setuptools import setup

setup(
    install_requires=[
        "colorama >= 0.4.4",
        "packaging >= 21.3",
        "requests >= 2.27.1",
        "pkginfo >= 1.8.1",
        "rfc3986 >= 2.0.0",
        "trove-classifiers >= 2022.1.6",
        'readme_renderer >= 32.0',
        'cmarkgfm >= 0.7.0',
    ],
    tests_require=[
        "tox >= 3.24.5",
    ],
)
