from setuptools import setup

setup(
    name='foundryWorldTools',
    version='0.3.1',
    packages=['foundryWorldTools'],
    package_data = {
        'foundryWorldTools': ['*.json']
    },
    include_package_data=True,
    install_requires=[
        'Click',
        'jsonlines',
    ],
    entry_points = {
        'console_scripts': ['fwt=foundryWorldTools.fwtCli:cli'],
    }
)
