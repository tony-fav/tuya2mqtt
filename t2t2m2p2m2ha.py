import os
import time

DEVICE_TYPE = os.getenv('DEVICE_TYPE', '').lower()

supported_devices = ['dekala_table_lamp', 'heimvision_night_light']
# supported_devices = ['dekala_table_lamp', 'heimvision_night_light', 'soulsens_night_light']

if DEVICE_TYPE in supported_devices:
    os.system('python ./devices/' + DEVICE_TYPE + '/driver.py')
else:
    print('Unknown DEVICE_TYPE: %s' % DEVICE_TYPE)
