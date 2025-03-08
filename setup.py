import io
import os
from typing import List
from setuptools import setup, find_packages

HERE = os.path.abspath(os.path.dirname(__file__))

def load_requirements(filename: str) -> List[str]:
    with io.open(
        os.path.join(HERE, filename), "rt", encoding="utf-8"
    ) as f:
        return [line.strip() for line in f if is_requirement(line)]

def is_requirement(line: str) -> bool:
    return not (line.strip() == "" or line.startswith("#"))

setup(
    name="openedx-optimize-course-images",
    version="1.0.0",
    description="A script to optimize course images in Open edX course exports.",
    author="EducateWorkforce",
    author_email="support@educateworkforce.com",
    url="https://github.com/CUCWD/openedx-optimize-course-images",
    packages=find_packages(),
    install_requires=load_requirements("requirements.txt"),
    entry_points={
        "console_scripts": [
            "optimize-course-images=optimize_course_images:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
