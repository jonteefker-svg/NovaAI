from setuptools import setup

APP = ['NOVA.py']
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'nova_icon.icns',
    'packages': ['customtkinter', 'ollama', 'requests', 'PIL', 'darkdetect', 'packaging'],
    'includes': ['json', 'threading', 'datetime', 'platform', 'random'],
    'excludes': [],
    'plist': {
        'CFBundleName': 'NOVA',
        'CFBundleDisplayName': 'NOVA AI',
        'CFBundleIdentifier': 'com.jefker.nova',
        'CFBundleVersion': '4.1.0',
        'LSMinimumSystemVersion': '10.13',
    },
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
