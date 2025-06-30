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

debug = False

if debug == True:
    import os
    def clear(): return os.system('cls' if os.name == 'nt' else 'clear')


REAL_GRID_POWER_TOPIC = "energy/Power"
REAL_SOLAR_POWER_TOPIC = "sim-data/Solar-Pwr"
BATTERY_WH = 16600
MIN_GRID_POWER = 50.0
MAX_INV_POWER = 2400.0
CHR_CNTRL_EFF = 0.9
INV_EFF = 0.9
BATT_EFF = 0.84

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
pred_solar_pwr = 0.0
delta_time = 0.0

# ----PWR Statistical Output Var
stat_solar_pwr = 0.0
stat_batt_pwr = 0.0

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
        global pred_solar_pwr, mqtt_grid_pwr, battery_cap_wh, started, pwr_msg
        if (msg.topic == REAL_SOLAR_POWER_TOPIC):
            if msg.payload != b'NaN':
                pred_solar_pwr = int(msg.payload)
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

    def send_pwr_mqtt():
        client.publish("sim-data/real-grid-pwr",
                       str(round(grid_pwr, 2)), 2, True)
        # client.publish("sim-data/net-pwr",
        #               str(round(net_pwr, 2)), 2, True)
        client.publish("sim-data/stat-batt-pwr",
                       str(round(stat_batt_pwr, 2)), 2, True)
        client.publish("sim-data/grid-pwr",
                       str(round(sim_grid_pwr, 2)), 2, True)
        client.publish("sim-data/stat-solar-pwr",
                       str(round(stat_solar_pwr, 2)), 2, True)

    def send_stats_mqtt():
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

    def int_energy():
        global battery_cap_wh, battery_in_wh, battery_out_wh, ha_out_grid_wh, ha_in_grid_wh, sim_solar_wh

        sim_solar_wh = integrate(
            sim_solar_wh, sim_solar_pwr*CHR_CNTRL_EFF*INV_EFF, delta_time)
        battery_cap_wh = integrate(battery_cap_wh, -sim_batt_pwr, delta_time)
        if (sim_batt_pwr < 0):
            battery_in_wh = integrate(
                battery_in_wh, -sim_batt_pwr*INV_EFF, delta_time)
        else:
            battery_out_wh = integrate(
                battery_out_wh, sim_batt_pwr*INV_EFF, delta_time)

        if (sim_grid_pwr < 0):
            ha_out_grid_wh = integrate(
                ha_out_grid_wh, -sim_grid_pwr, delta_time)
        else:
            ha_in_grid_wh = integrate(ha_in_grid_wh, sim_grid_pwr, delta_time)

    def power_calc():
        global grid_pwr, sim_batt_pwr, sim_grid_pwr, battery_state, sim_solar_pwr, stat_solar_pwr, stat_batt_pwr
        # print("--------------------------------------------")
        grid_pwr = mqtt_grid_pwr
        # print("GRID DATA", grid_pwr)
        sim_solar_pwr = pred_solar_pwr/INV_EFF
        stat_solar_pwr = sim_solar_pwr
        sim_solar_pwr = sim_solar_pwr*CHR_CNTRL_EFF
        # print("SOLAR PWR", sim_solar_pwr)
        req_out_inv_pwr = 0.0
        if grid_pwr < (MAX_INV_POWER+MIN_GRID_POWER):
            req_out_inv_pwr = grid_pwr - MIN_GRID_POWER
            if req_out_inv_pwr < 0:
                req_out_inv_pwr = 0.0
        else:
            req_out_inv_pwr = 800.0
        # print("R INV OUT", req_out_inv_pwr)
        req_in_inv_pwr = req_out_inv_pwr/INV_EFF
        # print("R INV IN", req_in_inv_pwr)
        req_battery_pwr = req_in_inv_pwr - sim_solar_pwr
        # print("R BATT OUT", req_battery_pwr)
        if req_battery_pwr > 0:
            if (battery_cap_wh > BATTERY_WH/10.0):
                battery_state = "DISCHARGING"
                sim_batt_pwr = req_battery_pwr/(1-(1-BATT_EFF)/2)
            else:
                battery_state = "EMPTY"
                sim_batt_pwr = 0
        else:
            if battery_cap_wh < BATTERY_WH:
                sim_batt_pwr = req_battery_pwr*(1-(1-BATT_EFF)/2)
                battery_state = "CHARGING"
            else:
                sim_batt_pwr = 0
                battery_state = "FULL"
        # print("REAL BATT PWR", sim_batt_pwr)
        if sim_batt_pwr < 0:
            stat_batt_pwr = sim_batt_pwr/(1-(1-BATT_EFF)/2)
            real_inv_pwr = (sim_solar_pwr+sim_batt_pwr /
                            (1-(1-BATT_EFF)/2))*INV_EFF
        else:
            stat_batt_pwr = sim_batt_pwr*BATT_EFF
            real_inv_pwr = (sim_solar_pwr+sim_batt_pwr *
                            (1-(1-BATT_EFF)/2))*INV_EFF

        if real_inv_pwr > 800:
            real_inv_pwr = 800

        # print("REAL INV OUT", real_inv_pwr)
        sim_grid_pwr = grid_pwr - real_inv_pwr
        # print("REAL GRID", sim_grid_pwr)

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

        power_calc()

        int_energy()

        battery_soc = battery_cap_wh/BATTERY_WH
        if pwr_msg == True:
            send_pwr_mqtt()
            pwr_msg = False

        if ((datetime.now()-last_update).total_seconds() > 10):
            last_update = datetime.now()
            send_stats_mqtt()

        if ((datetime.now()-last_loop_log).total_seconds() > 60):
            print("In loop... Cycle time:", delta_time.total_seconds(), "s")
            last_loop_log = datetime.now()

        if debug == True:
            clear()
            print("Sol pwr:", sim_solar_pwr, "\nSol Wh:", sim_solar_wh, "\nBatt Pwr:", sim_batt_pwr, "\nGrid Pwr", sim_grid_pwr, "\nBattery state:", battery_state,
                  "\nBattery SOC:", battery_soc, "\nBattery Cap Wh:", battery_cap_wh, "\nBatt In Wh:", battery_in_wh, "\nBatt Out Wh:", battery_out_wh, "\nGrid In Wh:", ha_in_grid_wh, "\nGrid Out Wh:", ha_out_grid_wh)

        cycle_time = datetime.now()-time_now

        if ((1-cycle_time.total_seconds()) > 0):
            time.sleep(1-cycle_time.total_seconds())
        else:
            print("Cycle time excedeed:", cycle_time.total_seconds)

        loop_last_time = time_now

except Exception as e:
    print(e)
    exit(100)
