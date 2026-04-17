
import math

# W = 115 + 38/60 + 59.63/3600
# E = 115 + 26/60 + 35.84/3600
# N = 51 + 15/60 + 6.62/3600
# S = 51 + 7/60 + 3.00/3600
# deg_per_meter_lat = 1 / 111320
# deg_per_meter_lng = 1 / (111320 * math.cos(math.radians((N + S) / 2)))
# N = N + deg_per_meter_lat * 400
# S = S + deg_per_meter_lat * 400
# print(f"center = {((N + S) / 2):.6f}, {((W + E) / 2):.6f}")



# Molde
# N = 62 + 45/60 + 23.86/3600
# E = 7 + 12/60 + 49.37/3600

# Hammerfest
N = 70 +40/60 + 30/3600
E = 23 + 41/60 + 24/3600

# Granada, Nicaragua
# N = 11 + 56/60 + 6.00/3600
# E = -85 - 57/60 - 54.00/3600

# Newcastle Upon Tyne, UK
N = 54 + 58/60
E = -1 - 36/60

#deg_per_meter_lat = 1 / 111320
#deg_per_meter_lng = 1 / (111320 * math.cos(math.radians(N/2)))
print(f"center = {N:.6f}, {E:.6f}")


