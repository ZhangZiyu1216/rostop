# setup.py
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='rostop',  
    version='0.1.0', 
    author='zzy',
    author_email='zhangziyu_1216@qq.com',
    license='MIT License',
    license_files=[],
    description='A modern, interactive TUI for monitoring ROS topics.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/ZhangZiyu1216/rostop', 

    packages=find_packages(where=".", exclude=("tests",)),
    
    install_requires=[
        'pyyaml',
        'rospy_message_converter', 
    ],
    
    entry_points={
        'console_scripts': [
            'rostop = rostop.cli:cli_main',
        ],
    },
    
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console :: Curses',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Scientific/Engineering',
        'Topic :: System :: Monitoring',
    ],
    python_requires='>=3.8',
)