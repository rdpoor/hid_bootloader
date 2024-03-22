from setuptools import setup, find_packages

setup(
    name='hid_bootloader',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'hid-bootloader=hid_bootloader.bl_main:main',
        ],
    },
    install_requires=[
        'hidapi'
    ],
    # Optional metadata
    author='R. D. Poor',
    author_email='rdpoor # gmail.com',
    description='Bootload a .hex file using the Microchip USB HID bootloader.',
    license='MIT',
    keywords='',
    url='http://github/rdpoor/hid_bootloader',
)
