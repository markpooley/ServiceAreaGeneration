# !/usr/bin/env python
# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------
# Name          : VisitAggregatorAndLocCalculator.py
# Author  		: Mark Pooley (mark-pooley@uiowa.edu)
# Link    		: http://www.ppc.uiowa.edu
# Date    		: 2015-01-26 11:56:18
# Version		: $1.0$
# Description	: Takes ZCTAs, Service Areas, and the Dyad Table used to create the Service Areas
# to calculate the Localization of Care (LOC) for each DSA.
# Addtionally, the pearson coefficient is determined
#-------------------------------------------------------------------------------------------------

###################################################################################################
#Import python modules
###################################################################################################
import os
import arcpy
from arcpy import env
import numpy
from operator import itemgetter
from collections import defaultdict

###################################################################################################
#Input Variable loading and environment declaration
###################################################################################################
ZCTAs = arcpy.GetParameterAsText(0)
ZCTA_Field = arcpy.GetParameterAsText(1)
Assigned_To_Field = arcpy.GetParameterAsText(2)
ServiceAreas = arcpy.GetParameterAsText(3)
DyadTable = arcpy.GetParameterAsText(4)
Visits_Field = arcpy.GetParameterAsText(5)
VisitsTotal_Field = arcpy.GetParameterAsText(6)

###################################################################################################
# Defining global functions
###################################################################################################


###################################################################################################
#Global variables to be used in process
###################################################################################################
ZCTA_FieldList = [f.name for f in arcpy.ListFields(ZCTAs)]
SeedList =[] # list of seeds
Assign_Dict = defaultdict(list) #dictionary of ZCTAs assigend to Seeds
DyadTable_FieldList = [f.name for f in arcpy.ListFields(DyadTable)] #create field list from Dyad Table
DyadRec_field = [f for f in DyadTable_FieldList if 'rec' in f.lower()][0] #find rec_ZCTA field within field list
DyadProv_field = [f for f in DyadTable_FieldList if 'prov' in f.lower()][0] #find prov_ZCTA field within field list

###################################################################################################
#Get a list of the seeds create a dictionary containing all the unique entries in the "Assigned_To"
#field and append all those areas assigned to them in the list for that entry in the dictionary.
###################################################################################################
with arcpy.da.SearchCursor(ZCTAs,[ZCTA_Field,Assigned_To_Field]) as cursor:
	for row in cursor:
		SeedList.append(row[1])
		#create a dictionary of assignments
		Assign_Dict[str(row[1])].append(str(row[0]))
		if row[1] == None:
			arcpy.AddMessage(row)

SeedList = list(set(SeedList))
arcpy.AddMessage("{0} seeds found".format(str(len(SeedList))))

###################################################################################################
#Add Fields to Service Area Feature Class
###################################################################################################
#arcpy.SetProgressor("step","message",0,#processLength,1)
ServiceAreas_FieldList = [f.name for f in arcpy.ListFields(ServiceAreas)] #lsit of fields in Service areas
FieldsToAdd = ["Visits_In","Visits_Out","Visits_Total","LOC"] #list of fields to add to Service Area
#check for existing fields
arcpy.SetProgressor("step","Adding fields to Service Areas feature class...",0,len(FieldsToAdd),1)
for item in FieldsToAdd:
	if item not in ServiceAreas_FieldList:
		if item != "LOC": #different data type for LOC field
			arcpy.AddField_management(ServiceAreas,item,"LONG")
		else:
			arcpy.AddField_management(ServiceAreas,item,"FLOAT")
		arcpy.SetProgressorPosition()
ServiceAreas_FieldList = [f.name for f in arcpy.ListFields(ServiceAreas)] #redefine after adding fields
####################################################################################################
#build a dictionary of recipients and total visits occuring within that recipient ZCTA. This is used
#for total visit aggregation in the service areas. It's faster and eaiser than using search cursors
####################################################################################################
visitDict = {}
with arcpy.da.SearchCursor(DyadTable,[DyadRec_field,VisitsTotal_Field]) as cursor:
	for row in cursor:
		visitDict[str(row[0])] = row[1]


###################################################################################################
#Find all care occuring within the Service Area, and the total care sought in all the ZCTAS within
# the service area to calculate LOC.
###################################################################################################

LOC_List = []
arcpy.SetProgressor("step","determining LOC for service areas...",0,len(Assign_Dict),1)
for key,values in Assign_Dict.iteritems():
	#tracking variables that need to be reset for each iteration
	Visits_In = 0
	Visits_Out = 0
	Visits_Total = 0

	dyadQuery = DyadProv_field + " = " + str(key)
	updateQuery = Assigned_To_Field + " = '" + str(key) + "'"
	ZCTA_List = values #just store values as a seperate list for easier tracking rember, the key is in the list

	#find all instances of visits occuring within the Service Area going to the seed as a provider
	with arcpy.da.SearchCursor(DyadTable,DyadTable_FieldList,dyadQuery) as cursor:
		for row in cursor:
			if str(row[DyadTable_FieldList.index(DyadRec_field)]) in ZCTA_List: #convert row to string!
				Visits_In += row[DyadTable_FieldList.index(Visits_Field)]


	#-------------------------------------------------------------------------------------------
	#use the visits dictionary to determine the max care occuring in a service area. The ZCTAs
	#assigned to the seed, and the seed are all in the value list, so aggregation of total care
	#is straight forward
	#-------------------------------------------------------------------------------------------
	for item in values:
		try:
			Visits_Total += visitDict[item]
		except KeyError:
			pass
	if Visits_Total == 0:
		arcpy.AddMessage('{0} generated 0 total visits'.format(key))

	#find instances of visits occuring between ZCTAs within the same service area where the provider
	#isn't the seed.
	for item in ZCTA_List:
		if item != key: #make sure to not count the seed twice
			Query =  DyadProv_field + " = " + item
			with arcpy.da.SearchCursor(DyadTable,DyadTable_FieldList,Query) as cursor:
				for row in cursor:
					if str(row[DyadTable_FieldList.index(DyadRec_field)]) in ZCTA_List:
						Visits_In += row[DyadTable_FieldList.index(Visits_Field)]



	#update rows in the Service Area feature class
	with arcpy.da.UpdateCursor(ServiceAreas,ServiceAreas_FieldList,updateQuery) as cursor:
		for row in cursor:
			row[ServiceAreas_FieldList.index("Visits_In")] = Visits_In
			row[ServiceAreas_FieldList.index("Visits_Total")] = Visits_Total
			row[ServiceAreas_FieldList.index("Visits_Out")] = Visits_Total - Visits_In
			row[ServiceAreas_FieldList.index("LOC")] = float(Visits_In) / float(Visits_Total)
			cursor.updateRow(row)#udpate rows
			LOC_List.append(row[ServiceAreas_FieldList.index("LOC")])
	arcpy.SetProgressorLabel("{0} Visits in {1}. {2} total visits.".format(str(Visits_In),str(key),str(Visits_Total)))
	arcpy.SetProgressorPosition()

###################################################################################################
#Determine pearson correlation coefficient of area and LOC
###################################################################################################
area = []
LOC = []
featureCount = int(arcpy.GetCount_management(ServiceAreas).getOutput(0))
area_index = ServiceAreas_FieldList.index([f for f in ServiceAreas_FieldList if 'area' in f.lower()][0])#get area index
LOC_index = ServiceAreas_FieldList.index([f for f in ServiceAreas_FieldList if 'loc' in f.lower()][0])#get LOC index

arcpy.SetProgressor("step","determining pearson coefficient of area to LOC...",0,featureCount,1)
with arcpy.da.SearchCursor(ServiceAreas,ServiceAreas_FieldList) as cursor:
	for row in cursor:
		area.append(row[area_index])
		LOC.append(row[LOC_index])
		arcpy.SetProgressorPosition()

correlation = numpy.corrcoef(area,LOC)[0,1]

###################################################################################################
#Final Output and cleaning of temp data/variables
###################################################################################################
arcpy.AddMessage("minimum LOC:{0} \nmaximum LOC: {1}".format(round(min(LOC_List),3),round(max(LOC_List),3)))
arcpy.AddMessage("correlation coefficient area to LOC: {0}".format(correlation))
arcpy.AddMessage("Process complete!")