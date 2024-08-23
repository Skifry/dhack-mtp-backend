from typing import List, Tuple
from pydantic import BaseModel, Field
import geojson
from collections import defaultdict
import math
import json
from app.data import schemas
import csv
from enum import Enum
import copy

LIVING_DENSITY = 45
WORKING_DENSITY = 35
LANE_COUNT_PMAX = {
    1: 1800,
    2: 3600,
    3: 4000,
    4: 2200 * 3.6,
    5: 2200 * 4.5,
    6: 2300 * 5.4,
    7: 2300 * 6.3,
    8: 2300 * 7.2
}
B8_PARAMETER = {
    5: 0.22,
    10: 0.44,
    20: 0.76,
    30: 0.88,
    40: 0.96,
    50: 0.98,
    60: 1,
    70: 1,
    80: 1,
    90: 1,
    100: 1,
    110: 1,
    120: 1
}

with open('app/data/metroPoints.json', 'r', encoding='cp1251') as f:
    metroPoints = geojson.load(f)

# with open('app/data/metroTraffic.json', 'r', encoding='cp1251') as f:
#     metroTraffic = json.load(f)

with open('app/data/roadFeatures.geojson', 'r') as f:
    roadFeatures = json.load(f)

metroTraffic = [row for row in csv.DictReader(open('app/data/metroTraffic.csv', 'r'), delimiter=';')]
# print(metroTraffic)

stBoundPoints = defaultdict(lambda: [])
for point in metroPoints:
    stBoundPoints[point['NameOfStation']].append((float(point['Latitude_WGS84']), float(point['Longitude_WGS84']),))

pointStations = {}
for station, points in stBoundPoints.items():
    x = [p[0] for p in points]
    y = [p[1] for p in points]
    centerP = (sum(x) / len(points), sum(y) / len(points))
    pointStations[station] = centerP

trafficStations = {}
for station in metroTraffic:
    if int(station['IncomingPassengers']) == 0:
        continue
    try:
        if int(station['Year']) == 2024 and station['Quarter'] == 'I квартал':
            trafficStations[station['NameOfStation']] = (int(station['IncomingPassengers']) / 90 / 1000) + (int(station['OutgoingPassengers']) / 90 / 1000)
    except ValueError:
        continue

class MetroStation(BaseModel):
    title: str
    loadPKH: float
    loadIncrease: int = Field(0)
    point: Tuple[float, float]
    used: bool = Field(False)

metroSt: List[MetroStation] = []
for station, point in pointStations.items():
    try:
        traffic = trafficStations[station]
    except KeyError:
        continue
    metroSt.append(MetroStation(
        title=station,
        loadPKH=traffic,
        point=point
    ))

def kmTwoPoints(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2) * 6371 / 100

def centerPoint(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    x = [p[0] for p in points]
    y = [p[1] for p in points]
    return (sum(x) / len(points), sum(y) / len(points))

def findClosestMetros(polybox: List[Tuple[float, float]], metroSta: List[MetroStation]) -> List[MetroStation]:
    goodStations = []
    centerPolyPoint = centerPoint(polybox)
    for station in metroSta:
        if kmTwoPoints(centerPolyPoint[0], centerPolyPoint[1], station.point[0], station.point[1]) <= 1.5: # TODO: make coefficient for moscow center approximateion
            goodStations.append(station)
            station.used = True
    
    return goodStations

def calcMetroCountAndAdd(metroList: List[MetroStation], Io: float, Ii: float) -> List[MetroStation]:
    I = (Io + Ii) / 1000 * 0.8
    totalLoad = sum([metro.loadPKH for metro in metroList])
    for metro in metroList:
        loadShare = metro.loadPKH / totalLoad
        pAmount = I * loadShare
        metro.loadIncrease = (pAmount) * 100 / metro.loadPKH
        metro.loadPKH += pAmount
    return metroList

class RoadSection(BaseModel):
    name: str
    lanes: int = Field(2)
    line: List[Tuple[float, float]]
    currentFlow: float
    maxFlow: float
    osmId: int
    used: bool = Field(False)
    
groads: List[RoadSection] = []
registredRoadNames = []

def findRoadIdxWithName(name: str) -> int:
    for idx, road in enumerate(groads):
        if road.name == name:
            return idx

for road in roadFeatures['features']:
    data = road['properties']
    if not data['NAME'] or not road['geometry']['type'] == 'LineString': continue
    geoline = []
    for point in road['geometry']['coordinates']:
        geoline.append((point[1], point[0], ))
    if data['NAME'] in registredRoadNames:
        roadIdx = findRoadIdxWithName(data['NAME'])
        if groads[roadIdx].line[-1] == geoline[0]:
            groads[roadIdx].line += geoline
        continue 
    lanes = 2 if not data['LANES'] else int(data['LANES'])

    if not data['MAXSPEED'] or data['MAXSPEED'] == 'RU:urban':
        maxspeed = 60
    elif data['MAXSPEED'] == 'RU:living_street':
        maxspeed = 20
    elif data['MAXSPEED'] == 'RU:rural':
        maxspeed = 10
    elif data['MAXSPEED'] == 'RU:motorway':
        maxspeed = 110
    else:
        maxspeed = int(data['MAXSPEED'])

    capacity = LANE_COUNT_PMAX[lanes] * 0.8 * B8_PARAMETER[maxspeed] * 1

    groads.append(
        RoadSection(
            name=data['NAME'],
            lanes=lanes,
            line=geoline,
            currentFlow=capacity * 0.4,
            maxFlow=capacity,
            osmId=data['OSM_ID']
        )
    )
    registredRoadNames.append(data['NAME'])

def calcSegmentDistanceKM(segment: List[Tuple[float, float]], point: Tuple[float, float]) -> float:
    xDelta = segment[1][0] - segment[0][0]
    yDelta = segment[1][1] - segment[0][1]
    try:
        u = (((point[0] - segment[0][0]) * xDelta) + ((point[1] - segment[0][1]) * yDelta)) / (xDelta ** 2 + yDelta ** 2)
    except ZeroDivisionError:
        return 200
    if u < 0:
        clsPoint = segment[0]
    elif u > 1:
        clsPoint = segment[1]
    else:
        clsPoint = ((segment[0][0] + u) * xDelta, (segment[0][1] + u) * yDelta)

    return kmTwoPoints(clsPoint[0], clsPoint[1], point[0], point[1])

def pickConnectedRoads(polygon: List[Tuple[float, float]], roadsW: List[RoadSection]):
    niceRoads = []
    for road in roadsW:
        polyCenter = centerPoint(polygon)
        roadCenter = centerPoint(road.line)
        if kmTwoPoints(polyCenter[0], polyCenter[1], roadCenter[0], roadCenter[1]) > 2: # TODO: make normal filtration for road probing
            continue
        
        brCon = True
        for Ridx in range(len(road.line) - 1):
            if not brCon: break
            for Pidx in range(len(polygon)):
                lR = road.line[Ridx]
                rR = road.line[Ridx + 1]
                lP = polygon[Pidx]
                rP = polygon[Pidx + 1] if len(polygon) < Pidx + 1 else polygon[0]
                PP = centerPoint([lP, rP])
                distance = calcSegmentDistanceKM([lR, rR], PP)
                if distance <= 0.10:
                    niceRoads.append(road)
                    road.used = True
                    brCon = False
                    break
    
    return niceRoads, roadsW

def calcCarCountAndAdd(roadList: List[RoadSection], Io: float, Ii: float) -> List[RoadSection]:
    I = (Io + Ii) * 0.2 / 1.8
    totalLoad = sum([road.maxFlow for road in roadList])
    for road in roadList:
        loadShare = road.maxFlow / totalLoad
        pAmount = I * loadShare
        road.currentFlow += pAmount
    return roadList

def calcTraffic(boxes: List[schemas.GeoBoundZK]) -> schemas.GeoCalculation:
    metroStCopy = copy.deepcopy(metroSt)
    roadCopy = copy.deepcopy(groads)
    for box in boxes:
        # calculating people count
        Io = box.livingSquare / LIVING_DENSITY
        Ii = box.workingSquare / WORKING_DENSITY

        # calculating transporting maximum
        # dayPeakIo = Io * 0.1
        # dayPeakIi = Ii * 0.35
        # eveningPeakIo = Ii * 0.35
        # eveningPeakIi = Io * 0.1
        midCountIo = Io * 0.05
        midCountIi = Ii * 0.1
        # mid2CountIo = midCountIi
        # mid2CountIi = midCountIo

        times = {
            'mid': (midCountIo, midCountIi),
        }

        metroLoad = {}
        carLoad = {}

        metroStations = findClosestMetros(box.points, metroStCopy)

        for time, values in times.items():
            metroLoad[time] = calcMetroCountAndAdd(metroStations, values[0], values[1])

        for station in metroLoad['mid']:
            for dbStation in metroStCopy:
                if dbStation.title == station.title:
                    dbStation.loadPKH = station.loadPKH
                    break

        roads, roadCopy = pickConnectedRoads(box.points, roadCopy)

        for time, values in times.items():
            carLoad[time] = calcCarCountAndAdd(roads, values[0], values[1])

        for road in carLoad['mid']:
            for dbRoad in roadCopy:
                if dbRoad.name == road.name:
                    dbRoad.currentFlow = road.currentFlow
                    break
    
    metroLoad = {
        'mid': []
    }
    for station in metroStCopy:
        if station.used:
            metroLoad['mid'].append(station)

    roadLoad = {
        'mid': []
    }
    for road in roadCopy:
        if road.used:
            roadLoad['mid'].append(road)

    return schemas.GeoCalculation(
        metroLoad=metroLoad,
        roadLoad=roadLoad
    )