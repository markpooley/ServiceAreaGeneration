# !/usr/bin/env python
# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------
# Name          : Service Area Generation.py
# Author  		: Mark Pooley (mark-pooley@uiowa.edu)
# Link    		: http://www.ppc.uiowa.edu
# Date    		: 2015-01-20 14:41:18
# Version		: $1.0$
# Description	: Takes ZCTAs and a Dyad table to create Base Service Areas that will likely need
# further analyasis and aggregation
#-------------------------------------------------------------------------------------------------

###################################################################################################
#Import python modules
###################################################################################################
import os
import arcpy
from arcpy import env
from itertools import *
from operator import itemgetter
from collections import defaultdict

###################################################################################################
#Input Variable loading and environment declaration
###################################################################################################
ZCTAs = arcpy.GetParameterAsText(0)
DyadTable = arcpy.GetParameterAsText(1)
DyadVisits_Field = arcpy.GetParameterAsText(2)
TotalVisits_Vield = arcpy.GetParameterAsText(3)
outputLocation = arcpy.GetParameterAsText(4)
output_Name = arcpy.GetParameterAsText(5)

featureCount = int(arcpy.GetCount_management(DyadTable).getOutput(0)) # get a count of rows in dyad table.

###################################################################################################
# Defining global functions
###################################################################################################

###################################################################################################
#Global variables to be used in process
###################################################################################################
#create field lists
arcpy.DeleteField_management(ZCTAs,"Assigned_To") #delete line when complete
ZCTAs_FieldList = [f.name for f in arcpy.ListFields(ZCTAs)] #create field list from ZCTAs
DyadTable_FieldList = [f.name for f in arcpy.ListFields(DyadTable)] #create field list from Dyad Table

#check for "Assign" in ZCTA Field List
if "Assign" not in ZCTAs_FieldList:
	arcpy.AddField_management(ZCTAs,"Assigned_To","TEXT")
	ZCTAs_FieldList = [f.name for f in arcpy.ListFields(ZCTAs)] #Re-declare field list from ZCTAs

#grab specific fields from field lists
ZCTA_field = [f for f in ZCTAs_FieldList if 'ZCTA' in f or 'ZIP' in f][0] #find ZCTA field within field list
DyadRec_field = [f for f in DyadTable_FieldList if 'REC' in f or 'rec' in f][0] #find rec_ZCTA field within field list
DyadProv_field = [f for f in DyadTable_FieldList if 'PROV' in f or'prov' in f][0] #find prov_ZCTA field within field list

#list to populate with matches of recipient and provider ZCTAs
seed_List = []
assign_dict = {}

###################################################################################################
#Find seeds by checking dyad table for instances where recipient and provider ZCTAs match, or where
#the first crterion is satisfied and the N_kids matches Max_kids....
###################################################################################################
arcpy.SetProgressor("step","Finding instances where recipient and provider ZCTA match...",0,featureCount,1)

with arcpy.da.SearchCursor(DyadTable,DyadTable_FieldList) as cursor:
	for row in cursor:
		if row[DyadTable_FieldList.index(DyadRec_field)] == row[DyadTable_FieldList.index(DyadProv_field)] and row[DyadTable_FieldList.index("N_kids")] == row[DyadTable_FieldList.index("Max_kids")]:
			seed_List.append(str(row[DyadTable_FieldList.index(DyadRec_field)]))
			assign_dict[str(row[DyadTable_FieldList.index(DyadRec_field)])] = str(row[DyadTable_FieldList.index(DyadRec_field)]) #update Assignment Dictionary
		arcpy.SetProgressorPosition() #update progressor positon
del row # delete row object
del cursor #delete cursor object

#remove any duplicates from seedlist, probaby not necessary, but it's cheap to check.
seed_List = set(seed_List)

arcpy.AddMessage("{0} seeds found from dyad table".format(str(len(seed_List))))

###################################################################################################
#update Assigned_To field with matches in the seed List
###################################################################################################
arcpy.SetProgressor("step","Updating 'Assigned_To' field with seeds...",0,len(seed_List),1)
with arcpy.da.UpdateCursor(ZCTAs,ZCTAs_FieldList) as cursor:
	for row in cursor:
		if row[ZCTAs_FieldList.index(ZCTA_field)] in seed_List:
			row[ZCTAs_FieldList.index("Assigned_To")] = row[ZCTAs_FieldList.index(ZCTA_field)]
			cursor.updateRow(row)
		arcpy.SetProgressorPosition()
del row # delete row object
del cursor #delete cursor object

#get count of unassigned ZCTAS
null_Count = 0
with arcpy.da.SearchCursor(ZCTAs,"Assigned_To","Assigned_To IS NULL") as cursor:
	for row in cursor:
		null_Count +=1
arcpy.AddMessage("{0} ZCTAs remain to be assigned".format(str(null_Count)))

###################################################################################################
#Generate a neighbor table and find all instances of seed neighbors where the provider ZCTA is the
#seed ZCTA and the dyad_Max in the dyad table is 1.
###################################################################################################
#generate neighbor table of ZCTAs
arcpy.AddMessage("Generating Neighbor Table for all features....")
NeighborTable = arcpy.PolygonNeighbors_analysis(ZCTAs,"Temp_NBR_Table", ZCTA_field,"NO_AREA_OVERLAP","BOTH_SIDES","#","METERS","SQUARE_METERS")
NBRTable_FieldList = [f.name for f in arcpy.ListFields(NeighborTable,"*")] #create neighbor table field list

nbrZCTA_Field = [f for f in NBRTable_FieldList if 'nbr' in f][0] #find nbr_ZCTA field within field list
srcZCTA_Field = [f for f in NBRTable_FieldList if 'src' in f][0] #find nbr_ZCTA field within field list

arcpy.SetProgressor("step","finding seed neighbors where dyad max = 1...",0,len(seed_List),1)
for i in seed_List:
	currentSeed = i # set current seed equal to i
	seedQuery = nbrZCTA_Field + " = '" + currentSeed + "' AND LENGTH > 0" #seed queary clause shared border length must be greater than 0
	dyadQuery = DyadProv_field + " = " + currentSeed  #dyad query

	temp_nbr_List = [] #temp list that will get re declared through each iteration

	#find all instances of neighbor ZCTAS being equal to current seed and populate list
	with arcpy.da.SearchCursor(NeighborTable,NBRTable_FieldList,seedQuery) as cursor:
		for row in cursor:
			temp_nbr_List.append(row[NBRTable_FieldList.index(srcZCTA_Field)]) #append src zctas to field list

	del row # delete row object
	del cursor #delete cursor object

	if '52333' in currentSeed:
		arcpy.AddMessage("52333 neighbor list: {0}".format(temp_nbr_List))

	#find instances where ZCTAs in the temp nbr list and the dyad max is equal to 1 - meaning that the most care
	#was received in the current seed ZCTA.
	with arcpy.da.SearchCursor(DyadTable,DyadTable_FieldList,dyadQuery) as cursor:
		for row in cursor:
			if row[DyadTable_FieldList.index(DyadRec_field)] in temp_nbr_List and row[DyadTable_FieldList.index("Dyad_max")] != 1:
				temp_nbr_List.remove(row[DyadTable_FieldList.index(DyadRec_field)])

	if '52333' in currentSeed:
		arcpy.AddMessage("52333 neighbor list: {0}".format(temp_nbr_List))

	del row # delete row object
	del cursor #delete cursor object

	with arcpy.da.UpdateCursor(ZCTAs,[ZCTA_field,"Assigned_To"]) as cursor:
		for row in cursor:
			#check that temp row is in nbr list, and it hasn't already been reassigned.
			if row[0] in temp_nbr_List and row[1] == None:
				row[1] = currentSeed
				if '52404' in row[0]:
					arcpy.AddMessage("52404 assigned to {0}".format(currentSeed))
				arcpy.SetProgressorLabel("{0} assigned to {1}".format(str(row[0]),str(currentSeed)))
				assign_dict[str(row[0])] = currentSeed #update Assignment Dictionary
				cursor.updateRow(row)

	del row # delete row object
	del cursor #delete cursor object

	arcpy.SetProgressorPosition()


#update null count after first assignment
null_Count = 0
unAssigned_List = []
with arcpy.da.SearchCursor(ZCTAs,[ZCTA_field,"Assigned_To"],"Assigned_To IS NULL") as cursor:
	for row in cursor:
		null_Count +=1
		unAssigned_List.append(row[0])
del cursor #delete cursor object
del row # delete row object
del temp_nbr_List

arcpy.AddMessage("{0} ZCTAs have been assigned".format(str(len(assign_dict))))
arcpy.AddMessage("{0} ZCTAs remain to be assigned".format(str(null_Count)))

###################################################################################################
#Go through unassigned ZCTAS and assign them to the best candidate neighbor using a series of
#dictionaries and lists to track what is going on. Find neighbors and their assignments. Assign
#remaining ZCTAS looking for Dyad_Max first, then the most visits. If the best nbr isn't in the
#generated lists, the current ZCTA is assigned to a neighbor based on most shared boundary.
###################################################################################################
if '52404' in unAssigned_List:
	arcpy.AddMessage("52404 has not yet ben assigned")
while len(unAssigned_List) > 0:
	arcpy.SetProgressor("step","finding best suited assignment for remaining ZCTAs...",0,len(unAssigned_List),1)
	for i in unAssigned_List:
		currentZCTA = i #assign current item to a variable
		ZCTAQuery = srcZCTA_Field + " = '" + currentZCTA + "' AND LENGTH > 0" #seed query clause
		dyadQuery = DyadRec_field + " = " + currentZCTA #dyad query
		temp_nbr_List = [] #list to track potential neighbor matches
		temp_key_List = [] #list to track where neighbors have been assigend to.
		dyadMax_nbr = 0 #temp variable to find the max care sought between a candidate
		nbr_Length = 0 #temp variable to compare shared boundary length of neighbors


		#find neighbors for null ZCTA that have already been assigned to a Service Area
		with arcpy.da.SearchCursor(NeighborTable,NBRTable_FieldList,ZCTAQuery) as cursor:
			for row in cursor:
				# if nbr has been assigned, put append to the temp list as candidate
				if row[NBRTable_FieldList.index(nbrZCTA_Field)] in assign_dict.keys():
					#create a list of neighbors that haven been assigned arleady
					temp_nbr_List.append(row[NBRTable_FieldList.index(nbrZCTA_Field)])
					#get what the potential neighbors have been assigned to and check that duplicates

					temp_key_List.append(assign_dict[row[NBRTable_FieldList.index(nbrZCTA_Field)]])
					#while trolling through nbr table, find the neighbor with the most shared border
					#and what it's assigned to.
					if row[NBRTable_FieldList.index("LENGTH")] > nbr_Length:
						best_nbr_Length = assign_dict[row[NBRTable_FieldList.index(nbrZCTA_Field)]]

		del row # delete row object
		del cursor #delete cursor object

		temp_key_List = list(set(temp_key_List)) #remove duplicates from list by creating a list from the set of the native list

		#check that the neighbor list is greater than 0. if not, pass.
		if len(temp_key_List) > 0:
			#if key list has length of one, only one potential candidate for assignment, so just go with it
			if len(temp_key_List) == 1:
				best_nbr = temp_key_List[0]
			else:

				#check what neighbors have been assigned to and look in the dyad table for care list
				with arcpy.da.SearchCursor(DyadTable,DyadTable_FieldList,dyadQuery) as cursor:
					for row in cursor:

						# if dyad pair is max - just assign it.
						if str(row[DyadTable_FieldList.index(DyadProv_field)]) in temp_key_List:
							if row[DyadTable_FieldList.index("Dyad_max")] == 1:
								best_nbr = str(row[DyadTable_FieldList.index(DyadProv_field)])

							else: #if dyad max condition isn't satisfied look for the highest n_kids
								if row[DyadTable_FieldList.index(DyadVisits_Field)] > dyadMax_nbr:
									dyadMax_nbr = row[DyadTable_FieldList.index(DyadVisits_Field)] #re assign dydad max
									best_nbr = row[DyadTable_FieldList.index(DyadProv_field)] #assign best neighbor

						else:
							pass

			#create assignment query to assign the current ZCTA to the best neighbor
			AssignQuery = ZCTA_field + " = '" + currentZCTA + "'"

			if best_nbr not in temp_key_List:
				best_nbr = best_nbr_Length
				arcpy.SetProgressorLabel("{0} assigned to {1} based on shared border".format(str(currentZCTA),str(best_nbr_Length)))

			#find entry of currnt ZCTA and update the Assigned_To field with the best neighbor
			with arcpy.da.UpdateCursor(ZCTAs,[ZCTA_field,"Assigned_To"],AssignQuery) as cursor:
				for row in cursor:
					#assign the currently unassigned ZCTA to what the best fitting neighbor has been assigned to.
					row[1] = best_nbr
					cursor.updateRow(row)
			del row # delete row object
			del cursor #delete cursor object

			assign_dict[currentZCTA] = str(best_nbr) #update assignment dictionary
			unAssigned_List.remove(currentZCTA) #remove current ZCTA from unAssigned List since it has been assigned
			arcpy.SetProgressorLabel("{0} assigned to: {1}".format(str(currentZCTA),str(assign_dict[str(best_nbr)])))

		else:
			arcpy.SetProgressorLabel("{0} passed, no suitable neighbors found yet".format(str(currentZCTA)))
			pass

		arcpy.SetProgressorPosition()
	arcpy.AddMessage("{0} ZCTAs remain unassigned".format(len(unAssigned_List)))
	arcpy.ResetProgressor() #reset progressor for next iteration through the above loop
###################################################################################################
#Dissolve Assigned ZCTAs into service areas
###################################################################################################

arcpy.SetProgressorLabel("Dissolving Assigned ZCTAs into Service Areas...")
ServiceAreas = arcpy.Dissolve_management(ZCTAs,output_Name,"Assigned_To")

###################################################################################################
#Final Output and cleaning of temp data/variables
###################################################################################################

arcpy.AddMessage("Process complete!")

# Replace a layer/table view name with a path to a dataset (which can be a layer file) or create the layer/table view within the script
# The following inputs are layers or table views: "Iowa_ZCTAs"
