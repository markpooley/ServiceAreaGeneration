# !/usr/bin/env python
# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------
# Name          : Dyad Table Creator
# Author  		: Mark Pooley (mark-pooley@uiowa.edu)
# Link    		: http://www.ppc.uiowa.edu
# Date    		: 2015-01-27 10:14:59
# Version		: $1.0$
# Description	: Description Here
#-------------------------------------------------------------------------------------------------

###################################################################################################
#Import python modules
###################################################################################################
import os
import arcpy
from arcpy import env
from operator import itemgetter
from collections import defaultdict

###################################################################################################
#Input Variable loading and environment declaration
###################################################################################################
ZCTAs = arcpy.GetParameterAsText(0)
ServiceAreas = arcpy.GetParameterAsText(1)
DyadTable = arcpy.GetParameterAsText(2)
OutputLocation = arcpy.GetParameterAsText(3)
OutputName = arcpy.GetParameterAsText(4)

###################################################################################################
# Defining global functions
###################################################################################################


###################################################################################################
#Global variables to be used in process
###################################################################################################
ZCTA_FieldList = [f.name for f in arcpy.ListFields(ZCTAs)]
Assigned_To_Field = [f for f in ZCTA_FieldList if 'Assign' in f][0]
ZCTA_Field = [f for f in ZCTA_FieldList if 'ZCTA' in f or "ZIP" in f][0]
SeedList =[] # list of seeds
Assign_Dict = {} #Dictionary of ZCTAs and assignments
ServiceArea_Dict = defaultdict(list) #dictionaryy of ZCTAs assigend to Seeds
DyadTable_FieldList = [f.name for f in arcpy.ListFields(DyadTable)] #create field list from Dyad Table
DyadRec_field = [f for f in DyadTable_FieldList if 'REC' in f or 'rec' in f][0] #find rec_ZCTA field within field list
DyadProv_field = [f for f in DyadTable_FieldList if 'PROV' in f or'prov' in f][0] #find prov_ZCTA field within field list
NewDyadTable = arcpy.CreateTable_management(OutputLocation,OutputName,DyadTable) #create new dyad table using old as template

#change field names in new dyad table
arcpy.AlterField_management(NewDyadTable,DyadRec_field,"REC_DSA")
arcpy.AlterField_management(NewDyadTable,DyadProv_field,"PROV_DSA")
arcpy.AlterField_management(NewDyadTable,"N_kids","Visits_Dyad")
arcpy.AlterField_management(NewDyadTable,"Util_0812","Visits_Total")
NewDyadTable_FieldList = [f.name for f in arcpy.ListFields(NewDyadTable)] #create field list from New Dyad Table

featureCount = int(arcpy.GetCount_management(ServiceAreas).getOutput(0))#count of DSAs
###################################################################################################
#get a list of the DSAs/seeds
###################################################################################################
with arcpy.da.SearchCursor(ZCTAs,[ZCTA_Field,Assigned_To_Field]) as cursor:
	for row in cursor:
		SeedList.append(row[1])
		Assign_Dict[row[0]] = row[1]#Dictionary of ZCTA assignments
		#create a dictionary of assignments
		if str(row[1]) in Assign_Dict.keys():
			ServiceArea_Dict[row[1]].append(str(row[0]))
		else:
			ServiceArea_Dict[row[1]].append(str(row[0]))


SeedList = list(set(SeedList)) #create a list from the set - removing duplicates
arcpy.AddMessage("{0} number of DSAs".format(featureCount))
arcpy.AddMessage("{0} seeds found".format(str(len(SeedList))))
###################################################################################################
#Create the Dyad Table
###################################################################################################
arcpy.SetProgressor("step","Creating New Dyad table",0,len(ServiceArea_Dict),1)

for key,values in ServiceArea_Dict.iteritems():
	tempDict = {}#temp dict to track where visits are going
	recDSA = key

	for item in values:
		#arcpy.AddMessage("key:{0}  value: {1}".format(recDSA,item))
		dyadRec_Query = DyadRec_field + " = " + item
		with arcpy.da.SearchCursor(DyadTable,DyadTable_FieldList,dyadRec_Query) as cursor:
			for row in cursor:

				#look at provider, and what ZCTA it's assigned to in the Assigned Dict. If it's
				#in the temp dictionary yet. If so, aggregate visits occuring
				if Assign_Dict[str(row[DyadTable_FieldList.index(DyadProv_field)])] in tempDict.keys():
					#if in temp Dictionary already, increment it by visits
					tempDict[Assign_Dict[str(row[DyadTable_FieldList.index(DyadProv_field)])]] += row[DyadTable_FieldList.index("N_kids")]
				#if it already exists and is found again, aggregate visits occuring there
				else:
					tempDict[str(row[DyadTable_FieldList.index(DyadProv_field)])] = row[DyadTable_FieldList.index("N_kids")]
				#arcpy.AddMessage(tempDict)
				arcpy.SetProgressorLabel("{0} entries found for {1}".format(len(tempDict),recDSA))

	with arcpy.da.InsertCursor(NewDyadTable,NewDyadTable_FieldList) as cursor:
		for k,v in tempDict.iteritems():
			cursor.insertRow((0,recDSA,k,v,0,None,None,None))

	arcpy.SetProgressorPosition()


###################################################################################################
#Process
###################################################################################################
#arcpy.SetProgressor("step","message",0,#processLength,1)

###################################################################################################
#Processes
###################################################################################################
#arcpy.SetProgressor("step","message",0,#processLength,1)

###################################################################################################
#Final Output and cleaning of temp data/variables
###################################################################################################
arcpy.AddMessage("Ouput Location: {0}".format(os.path.join(OutputLocation,OutputName)))
arcpy.AddMessage("Process complete!")