from setuptools import setup

setup(
    name='foundryWorldTools',
    version='0.4.8',
    packages=['foundryWorldTools'],
    package_data = {
        'foundryWorldTools': ['*.json']
    },
    include_package_data=True,
    install_requires=[
        'Click',
        'jsonlines',
        'pyyaml',
    ],
    entry_points = {
        'console_scripts': ['fwt=foundryWorldTools.fwtCli:cli'],
    }
)
