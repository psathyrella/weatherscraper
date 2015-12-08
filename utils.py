import math

freezing_point = 32.  # TODO handle deg C

variables = ['date', 'time-of-day', 'wind-speed', 'wind-direction', 'snow', 'rain', 'high', 'low']
wind_directions = ['E', 'ENE', 'NE', 'NNE', 'N', 'NNW', 'NW', 'WNW', 'W', 'WSW', 'SW', 'SSW', 'S', 'SSE', 'SE', 'ESE']
times_of_day = ['AM', 'PM', 'night']
weekdays = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')

# ----------------------------------------------------------------------------------------
def convert_wind_direction_to_angle(direction_str):
    index = wind_directions.index(direction_str)
    return float(index) * 2 * math.pi / len(wind_directions)

wind_angles = [convert_wind_direction_to_angle(direction) for direction in wind_directions]

# # ----------------------------------------------------------------------------------------
# def convert_wind_angle_to_direction_str(angle):
#     float_index = angle * len(wind_angles) / (2 * math.pi)
#     nearest_index = int(min(wind_angles, key=lambda x:abs(x-float_index)))
#     print '\n    ', float_index, nearest_index
#     return wind_directions[nearest_index]
