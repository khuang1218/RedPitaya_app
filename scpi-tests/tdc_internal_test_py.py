import time

import matplotlib.pyplot as plt

import redpitaya_scpi as scpi

RP_HOST = "169.254.77.151"  # <-- set this to your board

rp = scpi.scpi(RP_HOST, timeout=10.0)
print('connected to', RP_HOST)