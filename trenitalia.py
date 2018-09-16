#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
Author: Jacopo Jannone
Repository: https://github.com/jacopo-j/TrenitaliaAPI
License: MIT
Copyright: (c) 2018 Jacopo Jannone

Questo commento non deve MAI essere rimosso da questo file e deve
essere riportato integralmente nell'intestazione di qualunque programma
che faccia uso del codice di seguito o di parte di esso.

This comment may NOT be removed from this file and it must be present
on the header of any program using this code or any part of it.

------------------------------------------------------------------------

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''


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

class NoSolutionsFound(Exception):
    pass


class TrenitaliaBackend():
    VERSION = '5.0.1.0004'
    VERSION_SHORT = '5.0.1'
    HOST = 'https://gw71.mplat.trenitalia.it:444/'
    BACKEND_PATH = 'Trenitalia50/apps/services/api/Trenitalia/android/'
    INIT_URL = f'{HOST}{BACKEND_PATH}init'
    QUERY_URL = f'{HOST}{BACKEND_PATH}query'
    NIL = {"nil": True}

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

    def search_solution(self, origin, destination, dep_date, arr_date=None,
                        adults=1, children=0, train_type="All",
                        max_changes=99, limit=10):
        cur_index = 0
        if dep_date is None:
            depdrange = None
        else:
            depdrange = {"Start": self._build_date(dep_date), "End": None}
        if arr_date is None:
            arrdrange = None
        else:
            arrdrange = {"Start": self._build_date(arr_date), "End": None}
        while cur_index < limit:
            p = [{'AppVersion': self.VERSION_SHORT,
                  'Credentials': None,
                  'CredentialsAlias': None,
                  'DeviceId': self._device_id,
                  'Language': 'IT',
                  'PlantId': 'android',
                  'PointOfSaleId': 3,
                  'UnitOfWork': 0},
                  {'SearchTravelsRequest':
                        {'Body': {'PagingCriteria': {"StartIndex": cur_index,
                                                     "EndIndex": cur_index,
                                                     "SortDirection": None},
                                  "OriginStationId": origin,
                                  "DestinationStationId": destination,
                                  "DepartureDateTimeRange": depdrange,
                                  "ArrivalDateTimeRange": arrdrange,
                                  "ReturnDateTimeRange": None,
                                  "ArrivalReturnDateTimeRange": None,
                                  "IsReturn": False,
                                  "Passengers": {"PassengerQuantity": [
                                    {"Type": "Adult", "Quantity": adults},
                                    {"Type": "Child", "Quantity": children}]},
                                  "FidelityCardCode": None,
                                  "PostSaleCriteria": None,
                                  "TrainType": train_type,
                                  "MaxNumberOfChanges": str(max_changes)}}}]
            for i in range(2):
                r = self._session.post(self.QUERY_URL,
                                       data={"adapter": "SearchAndBuyAdapter",
                                             "procedure": "SearchTravels",
                                             "parameters": json.dumps(p)})
                result = json.loads(self._cleanup(r.text))
                if r.status_code == 200:
                    break
                if i > 0:
                    raise AuthenticationError("Authentication attempt failed "
                                              "after getting non 200 status code")
                self._authenticate(result)
            if result["statusCode"] == 500:
                if result["statusReason"].startswith("Nessuna soluzione"):
                    raise NoSolutionsFound()
                if result["statusReason"] == ("Errore restituito dal sistema "
                                              "centrale"):
                    return
            if (result["statusCode"] != 200):
                raise Non200StatusCode("Response statusCode {}: {}".format(
                                       result["statusCode"],
                                       result["statusReason"]))
            solution = (result["Envelope"]["Body"]["SearchTravelsResponse"]
                        ["Body"]["PageResult"]["TravelSolution"])
            output = {"changes": int(solution["Changes"]),
                           "destination":
                              {"name": solution["DestinationStation"]["Name"],
                               "id": solution["DestinationStation"]["Id"]},
                            "origin":
                              {"name": solution["OriginStation"]["Name"],
                               "id": solution["OriginStation"]["Id"]},
                            "duration": self._parse_time(
                                solution["TotalJourneyTime"]),
                            "arr_date": self._parse_date(
                                solution["ArrivalDateTime"]),
                            "dep_date": self._parse_date(
                                solution["DepartureDateTime"]),
                            "saleable": solution["IsSaleable"],
                            "solution_id": solution["SolutionId"],
                            "vehicles": [],
                            "min_points": Decimal(solution["MinLoyaltyPoints"])
                                if "MinLoyaltyPoints" in solution and
                                solution["MinLoyaltyPoints"] != self.NIL
                                else None,
                            "min_price": Decimal(solution["MinPrice"])
                                if solution["MinPrice"] != self.NIL else None}
            if isinstance(solution["Nodes"]["SolutionNode"], list):
                for v in solution["Nodes"]["SolutionNode"]:
                    vh_data = {"dep_date": self._parse_date(
                                            v["DepartureDateTime"]),
                               "arr_date": self._parse_date(
                                            v["ArrivalDateTime"]),
                               "category": (v["Train"]["CategoryCode"],
                                            v["Train"]["CategoryName"]),
                               "number": v["Train"]["Number"],
                               "arr_station":
                                    {"name": v["ArrivalStation"]["Name"],
                                     "id": v["ArrivalStation"]["Id"]},
                               "dep_station":
                                    {"name":v["DepartureStation"]["Name"],
                                     "id": v["DepartureStation"]["Id"]},
                               "id": v["Id"],
                               "duration": self._parse_time(
                                            v["JourneyDuration"])}
                    output["vehicles"].append(vh_data)
            else:
                v = solution["Nodes"]["SolutionNode"]
                vh_data = {"dep_date":self._parse_date(v["DepartureDateTime"]),
                           "arr_date": self._parse_date(v["ArrivalDateTime"]),
                           "category": (v["Train"]["CategoryCode"],
                                        v["Train"]["CategoryName"]),
                           "number": v["Train"]["Number"],
                           "arr_station": {"name": v["ArrivalStation"]["Name"],
                                           "id": v["ArrivalStation"]["Id"]},
                           "dep_station": {"name":v["DepartureStation"]["Name"],
                                           "id": v["DepartureStation"]["Id"]},
                           "id": v["Id"],
                           "duration": self._parse_time(v["JourneyDuration"])}
                output["vehicles"].append(vh_data)
            yield output
            cur_index += 1

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
pprint(list(tb.search_solution("830008224", "830012055", datetime(2018, 9, 15, 16, 0, 0), limit=10)))

