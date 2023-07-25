import arcpy
from arcpy.conversion import *
from arcpy.sa import *
import arpy.management
import arcpy.mp
import os


class Toolbox(object):
	def __init__(self):
	self.label - "Toolbox"
	self.alias = "Cost Surface"
	self.tools = [Costsurf]


class Costsurf(object):
	def __init__(self):
		"""Derives cost surface model from four criteria factors to calculate distance analysis between points."""
		self.category = 'Analysis'
		self.name = 'Cost Surface",
		self.label = 'Cost Surface'
		self.alias = 'Cost Surface'
		self.description = 'Compiles weighted criteria into a cost surface using a DEM, Landcover/Landuse, and road network data.'
		self.canRunInBackground = False

	def getParameterInfo(self):
		pdata = [
			['Terrain Dataset', 'terrain_dem', ['DERasterDataset', 'GPRasterLayer], 'Required', 'Input', None],
			['Landcover Dataset', 'landcover_data, [DEFeatureClass', 'GPFeatureLayer], 'Required', 'Input', None],
			['Roads', 'road_vector', ['DEFeatureClass', 'GPFeatureLayer], 'Required', 'Input', None],
			['Boundary Extent', 'extent', ['DEFeatureClass', 'GPFeatureLayer], 'Optional', 'Input', Advanced Options]
		]

		params = [
			arcpy.Parameter(
				displayName=d[0],
				name=d[1],
				datatype=d[2],
				parameterType=d[3],
				direction=d[4],
				category=d[5]) for d in [p for p in pdata]]
		return params

	def is Licensed(self):
		return True

	def updateParameters(self, parameters):
		return True

	def updateMessages(self, parameters):
		return True
	
	def execute((self, parameters, messages):
		arcpy.CheckOutExtension('Spatial')
		arcpy.CheckOutExtension('ImageAnalyst')
		arcpy.env.overwriteOutput = True

		p = arcpy.mp.ArcGISProject('CURRENT')
		db = p.defaultGeodatabase
		m = p.activeMap
		ws = arcpy.env.workspace

		dem = parameters[0].valueAsText
		lc = parameters[1].valueAsText
		road = parameters[2].valueAsText
		extent = parameters[3].valueAsText
		cellsize = "5"

		# Create hydrology feature raster
		FlowDir = FlowDirection(dem, "NORMAL", "", "D8")
		FlowAcc = FlowAccumulation(FlowDir, "", "FLOAT", "D8")
		StreamOrd = StreamOrder(FlowAcc, FlowDir, "STRAHLER")
		Streams = Reclassify(StreamOrd, 'VALUE', remap="1 5;2 5;3 5;4 5;5 2;6 2;7 2;NODATA 3", missing_values="NODATA"
		Streams.save("StreamOrder")

		# Calculate and Reclass Slope Raster
		slope = SurfaceParameter(dem, 'SLOPE', 'QUADRATIC', output_slope_measurement ='DEGREE')
		SlopeFact = Reclassify(slope, 'VALUE', remap="0 1 1;1 3 2;3 6 3;6 9 4;9 13 5;13 18 6;18 24 7;24 30 10;30 45 20;45 90 30", missing_values="NODATA")
		SlopeFact.save("Slope")

		# Create Road Raster Factor
		RoadRas = FeatureToRaster(road, 'FCODE', 'Road_ras', cell_size)
		# Reclass Roads for cost weight
		roadfact = Reclassify(RoadRas, 'FCODE', "AP010 1; AP030 1; AP050 1, NODATA 5", "NODATA")
		roadfact.save('Roads')

		# Reclassify VISNAV Landcover Raster (Standard 21 Classes)
		LandFact = Reclassify(lc, "VALUE", remap="0 NODATA; 1 2;2 3;3 4,4 1;5 1;6 2;7 1;8 3;9 5;10 5;11 5;12 2;13 5;14 2;16 5;17 5;18 5;19 5;20 2;21 2", missing_values="NODATA")
		LandFact.save('LULC')

		# Combine Raster Factors using Plus to create Cost Surface Model
		loc_ras = Plus(Streams, roadfact)
		land_ras = Plus(SlopeFact, Landfact)
		CostSurf = Plus(loc_ras, land_ras)
		CostSurf.save("Cost_Surface")
		m.addDataFromPath(CostSurf)
		
		
