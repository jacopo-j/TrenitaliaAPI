#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import uuid
import json
import time
import re
from datetime import datetime, timedelta
from decimal import Decimal
from pprint import pprint


class AuthenticationError(Exception):
    pass

class InvalidServerResponse(Exception):
    pass

class Non200StatusCode(Exception):
    pass

class TrainNotFoundException(Exception):
    pass

class MultipleTrainsFound(Exception):
    pass

class TrainCancelledException(Exception):
    pass


class TrenitaliaBackend():
    VERSION = '5.0.1.0004'
    VERSION_SHORT = '5.0.1'
    HOST = 'https://gw71.mplat.trenitalia.it:444/'
    BACKEND_PATH = 'Trenitalia50/apps/services/api/Trenitalia/android/'
    INIT_URL = f'{HOST}{BACKEND_PATH}init'
    QUERY_URL = f'{HOST}{BACKEND_PATH}query'

    def __init__(self):
        self._session = requests.session()
        self._session.headers.update({'x-wl-app-version': self.VERSION})
        self._device_id = str(uuid.uuid4())
        self._authenticate()

    def _cleanup(self, response):
        return response.replace("/*-secure-", "").replace("*/", "")

    def _authenticate(self, authd=None):
        if authd is None:
            r = self._session.post(self.INIT_URL)
            if (r.status_code != 401):
                raise InvalidServerResponse("Unexpected response from server "
                                            "while starting new session")
            authd = json.loads(self._cleanup(r.text))
        iid = authd["challenges"]["wl_antiXSRFRealm"]["WL-Instance-Id"]
        token = (authd["challenges"]["wl_deviceNoProvisioningRealm"]["token"])
        self._session.headers.update({"WL-Instance-Id": iid})
        authh = {'wl_deviceNoProvisioningRealm': {'ID': {'app':
                    {'id': 'Trenitalia', 'version': self.VERSION},
                     'custom': {},
                     'device': {'environment': 'android',
                     'id': self._device_id,
                     'model': 'unknown',
                     'os': '7.1.0'},
                     'token': token}}}
        r = self._session.post(self.INIT_URL,
                               headers={"Authorization": json.dumps(authh)})
        r.raise_for_status()
        result = json.loads(self._cleanup(r.text))
        if ("WL-Authentication-Success" not in result):
            raise AuthenticationError("Authentication failed")

    def _parse_time(self, string):
        values = re.findall(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", string)[0]
        total_seconds = 0
        if values[0] != "":
            total_seconds += int(values[0]) * 3600
        if values[1] != "":
            total_seconds += int(values[1]) * 60
        if values[2] != "":
            total_seconds += int(values[2])
        return timedelta(seconds=total_seconds)

    def _parse_date(self, string, timezone=True):
        if timezone:
            return datetime.strptime(string, "%Y-%m-%dT%H:%M:%S%z")
        return datetime.strptime(string, "%Y-%m-%dT%H:%M:%S")

    def _build_date(self, date):
        if date is None: return None
        if date.tzinfo is None:
            tzsec = time.localtime().tm_gmtoff
            tz = "{:+03d}:{:02d}".format(int(tzsec / 3600), abs(tzsec) % 3600)
            return datetime.strftime(date, "%Y-%m-%dT%H:%M:%S") + tz
        tzw = datetime.strftime(date, "%z")
        tz = "{}:{}".format(tzw[:3], tzw[3:])
        return datetime.strftime(date, "%Y-%m-%dT%H:%M:%S") + tz

    def _parse_stop_type(self, string):
        convert = {"Transit": "T",
                   "Departure": "P",
                   "Arrival": "A",
                   "Stop": "F"}
        return convert[string]

    def search_station(self, name, only_italian=False):
        p = [{'AppVersion': self.VERSION_SHORT,
              'Credentials': None,
              'CredentialsAlias': None,
              'DeviceId': self._device_id,
              'Language': 'IT',
              'PlantId': 'android',
              'PointOfSaleId': 3,
              'UnitOfWork': 0},
              {'GetStationsRequest': {'Body': {'Name': name}}},
              {'extractOnlyItalianStations': only_italian}]
        for i in range(2):
            r = self._session.post(self.QUERY_URL,
                                   data={"adapter": "StationsAdapter",
                                         "procedure": "GetStations",
                                         "parameters": json.dumps(p)})
            result = json.loads(self._cleanup(r.text))
            if r.status_code == 200:
                break
            if i > 0:
                raise AuthenticationError("Authentication attempt failed "
                                          "after getting non 200 status code")
            self._authenticate(result)
        if (result["statusCode"] != 200):
            raise Non200StatusCode("Response statusCode {}: {}".format(
                                   result["statusCode"],
                                   result["statusReason"]))
        data = (result["Envelope"]["Body"]["GetStationsResponse"]["Body"]
                      ["StationDetail"])
        output = []
        for station in data:
            output.append({"name": station["name"],
                           "lon": Decimal(station["longitude"])
                              if Decimal(station["longitude"]) != 0 else None,
                           "lat": Decimal(station["latitude"])
                              if Decimal(station["latitude"]) != 0 else None,
                           "id": int(station["stationcode"][2:]),
                           "railway": int(station["railwaycode"])})
        return data

    def train_info(self, number, dep_st=None, arr_st=None, dep_date=None):
        p = [{'AppVersion': self.VERSION_SHORT,
              'Credentials': None,
              'CredentialsAlias': None,
              'DeviceId': self._device_id,
              'Language': 'IT',
              'PlantId': 'android',
              'PointOfSaleId': 3,
              'UnitOfWork': 0},
              {'TrainRealtimeInfoRequest':
                    {'Body': {'ArrivalStationId': arr_st,
                              'DepartureDate': self._build_date(dep_date),
                              'DepartureStationId': dep_st,
                              'Train': {'CategoryCode': None,
                                        'CategoryName': None,
                                        'Notifiable': None,
                                        'Number': number}}}}]
        for i in range(2):
            r = self._session.post(self.QUERY_URL,
                                   data={"adapter": "TrainRealtimeInfoAdapter",
                                   "procedure": "TrainRealtimeInfo",
                                   "parameters": json.dumps(p)})
            result = json.loads(self._cleanup(r.text))
            if r.status_code == 200:
                break
            if i > 0:
                raise AuthenticationError("Authentication attempt failed "
                                          "after getting non 200 status code")
            self._authenticate(result)
        if result["statusCode"] == 500:
            if result["statusReason"] == "Treno non valido":
                raise TrainNotFoundException()
            if result["statusReason"] == "Il treno e' cancellato":
                raise TrainCancelledException()
        if (result["statusCode"] != 200):
            raise Non200StatusCode("Response statusCode {}: {}".format(
                                   result["statusCode"],
                                   result["statusReason"]))
        data = (result["Envelope"]["Body"]["TrainRealtimeInfoResponse"]["Body"]
                      ["RealtimeTrainInfoWithStops"])
        if isinstance(data, list):
            raise MultipleTrainsFound()
        chkpdate = self._parse_date(data["LastCheckPointTime"], timezone=False)
        if (chkpdate == datetime(1, 1, 1, 0, 0)):
            chkpdate = None
        if (data["LastReachedCheckPoint"] != "--"):
            chkloc = data["LastReachedCheckPoint"]
        else:
            chkloc = None
        output = {"category": (data["Train"]["CategoryCode"],
                               data["Train"]["CategoryName"]),
                  "number": data["Train"]["Number"],
                  "duration": self._parse_time(data["ScheduledDuration"]),
                  "delay": self._parse_time(data["Delay"]),
                  "viaggiatreno": data["IsViaggiaTreno"],
                  "checkpoint_date": chkpdate,
                  "checkpoint_locality": chkloc,
                  "stops": []}
        for stop in data["Stops"]["RealtimeTrainStop"]:
            if not isinstance(stop["ScheduledInfo"]["Departure"], dict):
                sch_dep = self._parse_date(stop["ScheduledInfo"]["Departure"])
            else:
                sch_dep = None
            if not isinstance(stop["ScheduledInfo"]["Arrival"], dict):
                sch_arr = self._parse_date(stop["ScheduledInfo"]["Arrival"])
            else:
                sch_arr = None
            if not isinstance(stop["ActualInfo"]["Departure"], dict):
                act_dep = self._parse_date(stop["ActualInfo"]["Departure"])
            else:
                act_dep = None
            if not isinstance(stop["ActualInfo"]["Arrival"], dict):
                act_arr = self._parse_date(stop["ActualInfo"]["Arrival"])
            else:
                act_arr = None
            if stop["ActualInfo"]["Track"] != "":
                sch_plat = stop["ActualInfo"]["Track"]
            else:
                sch_plat = None
            if stop["ActualInfo"]["Track"] != "":
                act_plat = stop["ActualInfo"]["Track"]
            else:
                act_plat = None
            stopdata = {"reached": stop["Reached"],
                        "type": self._parse_stop_type(stop["StopType"]),
                        "station": {"id": stop["Station"]["Id"],
                                    "lat": stop["Station"]["Latitude"],
                                    "lon": stop["Station"]["Longitude"],
                                    "name": stop["Station"]["Name"]},
                        "scheduled_dep": sch_dep,
                        "actual_dep": act_dep,
                        "scheduled_arr": sch_arr,
                        "actual_arr": act_arr,
                        "scheduled_plat": sch_plat,
                        "actual_plat": act_plat}
            output["stops"].append(stopdata)
        return output


tb = TrenitaliaBackend()
pprint(tb.search_station(""))


