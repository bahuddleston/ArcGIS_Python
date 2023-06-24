import arcpy
from arcpy.conversion import *
from arcpy.sa import *
import arcpy.management
import arcpy.mp
import os
import arcpy.ia
import arcpy.cartography
from arcpy.analysis import *
from arcpy import da


class Toolbox(object):
	def __init_(self):
		self.label = "Toolbox"
		self.alias = "CostPath"
		self.tools = [Costsurf]

class Costpath(object):
	def __init__(self):
		"""Derives least cost path between points using cost surface and created waypoints."""
		self.category = 'Analysis'
		self.name = 'Optimal Path'
		self.label = 'Optimal Path'
		self.alias = 'Optimal Path'
		self.description = 'Calculates optimal path between waypoints.'
		self.canRunInBackground = False

	def getParameterInfo(self):
		pdata = [
			['Cost Surface', 'cost_surf', ['DERasterDataset', 'GPRasterLayer'], 'Required', 'Input', None],
			['Output Name', 'output_name', 'GPString, 'Required', 'Input', None],
			['Waypoints', 'waypoints', ['DEFeatureClass', 'GPFeatureLayer'], 'Required', 'Input', None],
			['Corridor', 'corridor', 'GPBoolean', 'Optional', 'Input', 'Advanced Options']
		]

		params = [
			arcpy.Parameter(
				displayName=d[0],
				name=d[1],
				datatype=d[2],
				parameterType=d[3],
				direction=d[4]
				category=d[5]) for d in [p for p in pdata]
		params[3].value = True

		return params

	def isLicensed(self):
		return True
	
	def updateParameters(self, parameters):
		return True
	
	def updateMessages(self, parameters):
		return True

	def execute(self, parameters, messages):
		arcpy.CheckOutExtension('Spatial')
		arcpy.CheckOutExtension('ImageAnalyst')
		arcpy.env.overwriteOutput = True

		p = arcpy.mp.ArcGISProject('CURRENT')
		db = p.defaultGeodatabase
		m = p.activeMap
		ws = arcpy.env.workspace

		cost_surf = parameters[0].valueAsText
		output = os.path.join(db, parameters[1].valueAsText
		wp = parameters[2].valueAsText
		ca = parameters[3].valueAsText

		# Cost Path
		# Iterate and separate each waypoint into singular Feature Classes
		arcpy.AddMessage('Seperate Waypoints')
		WyPtsResult = []  # Empty list to store Waypoints
		with da.SearchCursor(wp, ["OBJECTID"]) as cursor:  # Searches for number of points in wp feature class
			for c, in cursor:
				where_clause = f"OBJECTID = {c}"
				wps = Select(wp, "wp_" + str(c), where_clause)  # selects and separates each point
				WyPtsResult.apend(wps)

		# Distance Accumulation
		count = 0
		dist_list = [] 
		arcpy.AddMessage("Create Distance Accumulation")
		for i in WyPtsResult:
			back_dir_ras = f'back_direction{count+1}'
			distacc = DistanceAccumulation(WyPtsResult[count], in_cost_raster=cost_surf, vertical_factor="BINARY 1-30 30", hrizontal_factor="BINARY 1 45", out_back_direction_raster=back_dir_ras, distance_method="PLANAR")
			distacc.save(f'DistAcc{count+1}')
			dist_list.append(distacc)
			if count >= len(WyPtsResult)-1:
				break
			arcpy.AddMessage("Creating Optimal Path...")
			back_dir = back_dir_ras
			op = OptimalPathAsLine(WyPtsResult[count+1], distacc, back_dir, out_polyline_features=f"op_path{count+1}", path_type="EACH ZONE", create_network_paths="DESTINATIONS_TO_SOURCES")
			
			arcpy.AddMessage("Smoothing Line Features...")
			TruePath = arcpy.cartography.SmoothLine(in_features=op, out_feature_class=output + str(count+1), algorithm="PAEK", tolerance=100, endpoint_option="NO_FIXED, error_option="NO_CHECK")
			count = count +1
			arcpy.AddMessage(f"{TruePath} complete...")
			m.addDataFromPath(TruePath)

		# Create Corridor Raster
		if ca == 'true':
			arcpy.AddMessage("Creating Corridor...")
			cor_list = []
			count = 0
			for c in dist_list:
				if count >= len(WyPtsResult)-1:
					break
				corridor_result = Corridor(dist_list[count], dist_list[count+1])
				corridor_result.save(f"corridor{count+1}")
				cor_res = m.addDataFromPath(corridor_result)
				count = count + 1
			# Update Corridor Symbology
			for lyr in cor_list:
				arpy.AddMessage("Updating Symbology...")
				sym = lyr.symbology
				sym.colorizer.stretchType = 'MiniumMaximum'
				sym.cororizer.colorRamp = p.listColorRamps('Temperature')[0]
				sym.colorizer.noDataColor = {'RGB': [0, 0, 0, 0]}
				sym.colorizer.minLabel = "Most Likely"
				sym.colorizer.maxLabel = "Less Likely"
				lyr.symbology = sym