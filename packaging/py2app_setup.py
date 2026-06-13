"""
py2app setup script for Prompt Engineering Platform macOS application.
Build with: python packaging/py2app_setup.py py2app
"""
from setuptools import setup

APP = ['src/macos/app.py']
DATA_FILES = [
    ('src/web/static', ['src/web/static/index.html']),
]
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'CFBundleName': 'Prompt Engineering',
        'CFBundleDisplayName': 'Prompt Engineering',
        'CFBundleIdentifier': 'com.promptengineering.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': 'MIT License',
    },
    'packages': [
        'fastapi', 'uvicorn', 'pydantic', 'starlette',
        'jinja2', 'yaml', 'rich',
    ],
    'includes': [
        'tkinter', 'json', 'threading', 'webbrowser', 'sqlite3',
        'src.web.app', 'database', 'evaluator', 'models', 'template_engine',
    ],
    'excludes': ['numpy', 'torch'],
}

setup(
    name='Prompt Engineering',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
