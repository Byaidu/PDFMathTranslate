import sys
from pathlib import Path

from setuptools import setup

setup(
    name="pdf2zh",
    description="Latex PDF Translater",
    license="MIT",
    author="Byaidu",
    author_email="byaidux@gmail.com",
    url="https://github.com/Byaidu/PDFMathTranslate",
    setuptools_git_versioning={
        "enabled": True,
    },
    setup_requires=["setuptools-git-versioning"],
    packages=["pdf2zh"],
    install_requires=[
        "charset-normalizer >= 2.0.0",
        "cryptography >= 36.0.0",
        "mtranslate",
        "pymupdf",
        "tqdm",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    entry_points={
        'console_scripts': [
            'pdf2zh=pdf2zh.pdf2zh:main',
        ]
    },
)
