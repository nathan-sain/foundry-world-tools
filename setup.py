from setuptools import setup

setup(
    name='foundryWorldTools',
    version='0.2',
    packages=['foundryWorldTools'],
    include_package_data=True,
    install_requires=[
        'Click',
        'jsonlines',
    ]
)