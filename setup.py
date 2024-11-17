from pathlib import Path
from pdf2zh import __version__, __author__
from setuptools import setup

root_dir = Path(__file__).parent
with open(root_dir / "README.md", encoding='utf-8') as f:
    readme = f.read()

setup(
    name="pdf2zh",
    long_description=readme,
    long_description_content_type="text/markdown",
    description="Latex PDF Translator",
    license="AGPLv3",
    version=__version__,
    author=__author__,
    author_email="byaidux@gmail.com",
    url="https://github.com/Byaidu/PDFMathTranslate",
    packages=["pdf2zh"],
    install_requires=[
        "charset-normalizer",
        "cryptography",
        "requests",
        "pymupdf",
        "tqdm",
        "tenacity",
        "doclayout-yolo",
        "numpy",
        "ollama",
        "deepl<1.19.1",
        "openai",
        "azure-ai-translation-text<=1.0.1",
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
