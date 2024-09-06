import sys
from pathlib import Path

from setuptools import setup

root_dir = Path(__file__).parent
with open(root_dir / "README.md", encoding='utf-8') as f:
    readme = f.read()

setup(
    name="pdf2zh",
    long_description=readme,
    long_description_content_type="text/markdown",
    description="Latex PDF Translator",
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
