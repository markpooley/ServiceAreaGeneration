# Service Area Generation
After using the Pre Processing tools, this toolset can be used to create service areas, re create dyad tables, and aggregate service areas based on user defined criteria

## 1. Serivice Area Generator
ZCTAs and a dyad table of recipient and provider ZCTAs are required to generate base DSAs. Service areas are generated in the following method

  1. Seeds are found by identifying instances where the recipient and provider ZCTA are the same, and the dyad max = 1 (the maximum number of visits occured in between this dyad)

  2. All neighbors to the seeds are found that share the same provider ZCTA as the neighboring seed. Neighbors are assigned accordingly

  3. The remaining unassigned ZCTAs are assigned to a service area in the following manner

    1. If the dyad max occured between an unassigned ZCTA and a neighbor, or the ZCTA the neighbor is assigned to - it is assigned accordingly

    2. Otherwise, the unassigned ZCTA is assigned to the neighbor where the most visits occured
    
## 2. Visit Aggregator and Localization of Care Calculator
Takes ZCTAs, corresponding Service Areas, and a Dyad table to aggregate visits and calculate LOC for each service area

## 3. Dyad Table Creator
Uses newly created service areas to generate a new dyad table of care occuring between service areas


