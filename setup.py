from setuptools import setup

setup(
    name='foundryWorldTools',
    version='0.1',
    packages=['foundryWorldTools'],
    include_package_data=True,
    install_requires=[
        'Click',
        'jmespath',
    ],
    entry_points = {
        'console_scripts': ['fwt=foundryWorldTools.fwtCli:cli'],
    }
)