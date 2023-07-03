"""
Copyright (C) 2023  Marco Fabbroni (marco.fabbroni@outlook.it)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import paho.mqtt.client as mqtt
import time
from datetime import datetime

debug = True

if debug == True:
    import os
    def clear(): return os.system('cls' if os.name == 'nt' else 'clear')


REAL_GRID_POWER_TOPIC = "energy/Power"
REAL_SOLAR_POWER_TOPIC = "sim-data/Solar-Pwr"
BATTERY_WH = 2400
MIN_GRID_POWER = 50.0

sim_solar_wh = 0.0
ha_in_grid_wh = 0.0
ha_out_grid_wh = 0.0
battery_cap_wh = 0.0
battery_soc = 0.1
battery_in_wh = 0.0
battery_out_wh = 0.0
battery_state = "EMPTY"
sim_batt_pwr = 0.0
mqtt_grid_pwr = 0.0
grid_pwr = 0.0
sim_grid_pwr = 0.0
sim_solar_pwr = 0.0

started = False

pwr_msg = False

try:

    def integrate(state, value, delta_time):
        return state+float(value)*float(delta_time.total_seconds())/3600.0

    def on_connect(client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        client.subscribe(REAL_GRID_POWER_TOPIC)
        client.subscribe(REAL_SOLAR_POWER_TOPIC)
        client.subscribe("sim-data/battery-wh")

    def on_message(client, userdata, msg):
        global sim_solar_pwr, mqtt_grid_pwr, battery_cap_wh, started, pwr_msg
        if (msg.topic == REAL_SOLAR_POWER_TOPIC):
            if msg.payload != b'NaN':
                sim_solar_pwr = int(msg.payload)
                pwr_msg = True
            else:
                sim_solar_pwr = 0
                pwr_msg = True
                print("Solar Pwr is NaN")

        elif (msg.topic == REAL_GRID_POWER_TOPIC):
            if msg.payload != b'NaN':
                mqtt_grid_pwr = int(msg.payload)
                pwr_msg = True
            else:
                mqtt_grid_pwr = 0
                pwr_msg = True
                print("Grid Pwr is NaN")
        elif (msg.topic == "sim-data/battery-wh"):
            print("Battery state received")
            if (started == False):
                battery_cap_wh = float(msg.payload)
                started = True
                print("Battery state saved")
            else:
                print("Sim already warm, discarding battery state")

            client.unsubscribe("sim-data/battery-wh")

    def on_disconnect(client, userdata, rc):
        print("mqtt disconnected")

    try:
        print("mqtt connection setup...")
        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        client.connect("192.168.20.20", 1883, 60)
        client.reconnect_delay_set(1, 10)
        client.loop_start()
        print("First connection try...")
        last_conn_msg = datetime.now()
        while not client.is_connected():
            if ((datetime.now()-last_conn_msg).total_seconds() > 10):
                print("Connecting...")
                last_loop_log = datetime.now()
            time.sleep(0.1)

    except Exception as e:
        print("Startup Exception:")
        print(e)
        exit(999)

    print("App started")

    loop_last_time = datetime.now()
    last_update = datetime.now()
    last_loop_log = datetime.utcnow()
    while True:
        time_now = datetime.now()
        delta_time = time_now-loop_last_time
        grid_pwr = mqtt_grid_pwr
        sim_solar_wh = integrate(sim_solar_wh, sim_solar_pwr, delta_time)
        net_pwr = grid_pwr-sim_solar_pwr
        batt_discharge_limit = 800-sim_solar_pwr
        if (net_pwr < 0):
            if (battery_cap_wh < BATTERY_WH):
                sim_grid_pwr = MIN_GRID_POWER
                sim_batt_pwr = net_pwr-MIN_GRID_POWER
                battery_state = "CHARGING"
            else:
                sim_batt_pwr = 0.0
                sim_grid_pwr = net_pwr
                battery_state = "FULL"
        else:
            if (battery_cap_wh > BATTERY_WH/10.0):
                if (net_pwr > batt_discharge_limit):
                    sim_batt_pwr = batt_discharge_limit
                    sim_grid_pwr = grid_pwr - 800
                    battery_state = "MAX DISCHARGING"
                else:
                    sim_batt_pwr = net_pwr+MIN_GRID_POWER
                    sim_grid_pwr = MIN_GRID_POWER
                    battery_state = "DISCHARGING"
            else:
                sim_batt_pwr = 0.0
                sim_grid_pwr = net_pwr
                battery_state = "EMPTY"

        battery_cap_wh = integrate(battery_cap_wh, -sim_batt_pwr, delta_time)
        if (sim_batt_pwr < 0):
            battery_in_wh = integrate(battery_in_wh, -sim_batt_pwr, delta_time)
        else:
            battery_out_wh = integrate(
                battery_out_wh, sim_batt_pwr, delta_time)

        if (sim_grid_pwr < 0):
            ha_out_grid_wh = integrate(
                ha_out_grid_wh, -sim_grid_pwr, delta_time)
        else:
            ha_in_grid_wh = integrate(ha_in_grid_wh, sim_grid_pwr, delta_time)

        battery_soc = battery_cap_wh/BATTERY_WH
        if pwr_msg == True:
            client.publish("sim-data/real-grid-pwr",
                           str(round(grid_pwr, 2)), 2, True)
            client.publish("sim-data/net-pwr",
                           str(round(net_pwr, 2)), 2, True)
            client.publish("sim-data/batt-pwr",
                           str(round(sim_batt_pwr, 2)), 2, True)
            client.publish("sim-data/grid-pwr",
                           str(round(sim_grid_pwr, 2)), 2, True)
            pwr_msg = False

        if ((datetime.now()-last_update).total_seconds() > 10):
            last_update = datetime.now()
            client.publish("sim-data/solar-wh",
                           str(round(sim_solar_wh, 2)), 2, True)
            client.publish("sim-data/battery-state",
                           battery_state, 2, True)
            client.publish("sim-data/battery-soc",
                           str(round(battery_soc*100, 2)), 2, True)
            client.publish("sim-data/battery-wh",
                           str(round(battery_cap_wh, 2)), 2, True)
            client.publish("sim-data/battery-in-wh",
                           str(round(battery_in_wh, 2)), 2, True)
            client.publish("sim-data/battery-out-wh",
                           str(round(battery_out_wh, 2)), 2, True)
            client.publish("sim-data/in-grid-wh",
                           str(round(ha_in_grid_wh, 2)), 2, True)
            client.publish("sim-data/out-grid-wh",
                           str(round(ha_out_grid_wh, 2)), 2, True)

        if ((datetime.now()-last_loop_log).total_seconds() > 60):
            print("In loop... Cycle time:", delta_time.total_seconds(), "s")
            last_loop_log = datetime.now()

        if debug == True:
            clear()
            print("Sol pwr:", sim_solar_pwr, "\nSol Wh:", sim_solar_wh, "\nNet pwr:",
                  net_pwr, "\nBatt Pwr:", sim_batt_pwr, "\nMax Batt:", batt_discharge_limit, "\nGrid Pwr", sim_grid_pwr, "\nBattery state:", battery_state, "\nBattery SOC:", battery_soc, "\nBattery Cap Wh:", battery_cap_wh, "\nBatt In Wh:", battery_in_wh, "\nBatt Out Wh:", battery_out_wh, "\nGrid In Wh:", ha_in_grid_wh, "\nGrid Out Wh:", ha_out_grid_wh)

        cycle_time = datetime.now()-time_now

        if ((1-cycle_time.total_seconds()) > 0):
            time.sleep(1-cycle_time.total_seconds())
        else:
            print("Cycle time excedeed:", cycle_time.total_seconds)

        loop_last_time = time_now

except Exception as e:
    print(e)
    exit(100)
