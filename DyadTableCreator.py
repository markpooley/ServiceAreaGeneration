# !/usr/bin/env python
# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------
# Name          : DyadTableCreator.py
# Author  		: Mark Pooley (mark-pooley@uiowa.edu)
# Link    		: http://www.ppc.uiowa.edu
# Date    		: 2015-01-27 10:14:59
# Version		: $1.0$
# Description	: Generates a new Dyad Table from the Service Areas created in using the Service area
# Generator script/tool. The Dyad table and ZCTAs used are needed as well. The new Dyad table
# is written to a user specified location.
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
ZCTAs = arcpy.GetParameterAsText(0) #base features used to create service areas
ZCTA_Field = arcpy.GetParameterAsText(1) #unique Identifier field for base features
ServiceAreas = arcpy.GetParameterAsText(2) # Service areas generated from base features
DyadTable = arcpy.GetParameterAsText(3) #dyad table used to create service areas from base features
OutputLocation = arcpy.GetParameterAsText(4) #location of new dyad Table
OutputName = arcpy.GetParameterAsText(5) #name of new dyad table

###################################################################################################
# Defining global functions
###################################################################################################


###################################################################################################
#Global variables to be used in process
###################################################################################################
ZCTA_FieldList = [f.name for f in arcpy.ListFields(ZCTAs)]
Assigned_To_Field = [f for f in ZCTA_FieldList if 'Assign_To' in f][0] #field of assignments
SeedList =[] # list of seeds
Assign_Dict = {} #Dictionary of ZCTAs and assignments
ServiceArea_Dict = defaultdict(list) #dictionaryy of ZCTAs assigend to Seeds
DyadTable_FieldList = [f.name for f in arcpy.ListFields(DyadTable)] #create field list from Dyad Table
DyadRec_field = [f for f in DyadTable_FieldList if 'rec' in f.lower()][0] #find rec_ZCTA field within field list
DyadProv_field = [f for f in DyadTable_FieldList if 'prov' in f.lower()][0] #find prov_ZCTA field within field list
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
		Assign_Dict[row[0]].append(row[1])#Dictionary of ZCTA assignments
		ServiceArea_Dict[row[1]].append(str(row[0])) #create a dictionary of assignments

SeedList = list(set(SeedList)) #create a list from the set - removing duplicates
arcpy.AddMessage("Number of DSAs: {0}".format(featureCount))
###################################################################################################
#Create the Dyad Table
###################################################################################################
arcpy.SetProgressor("step","Creating New Dyad table",0,len(ServiceArea_Dict),1)
prov_Index = DyadTable_FieldList.index(DyadProv_field)
rec_Index = DyadTable_FieldList.index(DyadRec_field)

for key,values in ServiceArea_Dict.iteritems():
	tempDict = {}#temp dict to track where visits are going
	recDSA = key

	for item in values:
		#arcpy.AddMessage("key:{0}  value: {1}".format(recDSA,item))
		dyadRec_Query = DyadRec_field + " = " + item
		with arcpy.da.SearchCursor(DyadTable,DyadTable_FieldList,dyadRec_Query) as cursor:
			for row in cursor:
				if str(row[prov_Index]) in Assign_Dict.keys():#check that provider has a key in the assignment dictionary
					#look at provider, and what ZCTA it's assigned to in the Assigned Dict. If it's
					#in the temp dictionary yet. If so, aggregate visits occuring
					if Assign_Dict[str(row[prov_Index])] in tempDict.keys():
						#if in temp Dictionary already, increment it by visits
						tempDict[Assign_Dict[str(row[prov_Index])]] += row[DyadTable_FieldList.index("N_kids")]
					#if it already exists and is found again, aggregate visits occuring there
					else:
						tempDict[str(row[prov_Index])] = row[DyadTable_FieldList.index("N_kids")]
					#arcpy.AddMessage(tempDict)
					arcpy.SetProgressorLabel("{0} entries found for {1}".format(len(tempDict),recDSA))
				else:
					arcpy.SetProgressorLabel("{0} not found in assignment dictionary".format(row[prov_Index]))

	with arcpy.da.InsertCursor(NewDyadTable,NewDyadTable_FieldList) as cursor:
		for k,v in tempDict.iteritems():
			cursor.insertRow((0,recDSA,k,v,0,None,None))

	arcpy.SetProgressorPosition()
###################################################################################################
#Get indices and generate a list of unique providers
###################################################################################################
featureCount = int(arcpy.GetCount_management(NewDyadTable).getOutput(0))
#-------------------------------------------------------------------------------------------
#get indices of fields that will be needed in search cursor
#-------------------------------------------------------------------------------------------
rec_Index = NewDyadTable_FieldList.index("REC_DSA")
prov_Index = NewDyadTable_FieldList.index("PROV_DSA")
visits_Index = NewDyadTable_FieldList.index("Visits_Dyad")
max_Index = NewDyadTable_FieldList.index("Max_kids")
dyad_max_Index = NewDyadTable_FieldList.index("Dyad_max")
VisitsTotal_Index = NewDyadTable_FieldList.index("Visits_Total")

recList = set() #declare list of recipient ZCTAS
arcpy.SetProgressor("step","Generating list of recipient DSAs..",0,featureCount,1)
with arcpy.da.SearchCursor(NewDyadTable,NewDyadTable_FieldList) as cursor:
	for row in cursor:
		recList.add(row[rec_Index])

recList = list(recList)#convert set to a list

###################################################################################################
#Update the max visits, number of utilizers and max dyad fields
###################################################################################################
arcpy.SetProgressor("step","Updating max visits, number of utilizers and max dyad fields...",0,len(recList),1)
#loop through list and
for i in recList:
	recQuery = "REC_DSA = " + str(i) #query
	maxVisits = 0
	utilizers = 0
	#aggregate visits and find the max number of visits
	with arcpy.da.SearchCursor(NewDyadTable,NewDyadTable_FieldList,recQuery) as cursor:
		for row in cursor:
			utilizers += row[visits_Index] #aggregate visits for th enumber of uitlizers
			if row[visits_Index] > maxVisits:
				maxVisits = row[visits_Index]

	#update the fields
	with arcpy.da.UpdateCursor(NewDyadTable,NewDyadTable_FieldList,recQuery) as cursor:
		for row in cursor:
			row[max_Index] = maxVisits
			row[VisitsTotal_Index] = utilizers
			#assign the max accordingly
			if row[visits_Index] == maxVisits:
				row[dyad_max_Index] = 1
			else:
				row[dyad_max_Index] = 0
			cursor.updateRow(row)

	arcpy.SetProgressorPosition()

###################################################################################################
#Final Output and cleaning of temp data/variables
###################################################################################################
arcpy.AddMessage("Ouput Location: {0}".format(os.path.join(OutputLocation,OutputName)))
arcpy.AddMessage("Process complete!")