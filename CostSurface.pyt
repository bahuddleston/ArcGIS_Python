import arcpy, sys, os, json
from arcpy.management import *
from arcpy.sa import *
from arcpy.conversion import *
import arcpy.mp

# Globals
def get_config():
	cfg_file = os.path.join(os.path.dirname(__file__), 'scripts', 'cfg', 'cost_config.json')
	with open(cfg_file) as data:
		cfg = json.load(data)
		return cfg

CFG = get_config()
PLATFORMS = CFG["platforms"]

sys.dont_write_bytecode = True
class Toolbox(object):
	def __init__(self):
		self.label = "Toolbox"
		self.alias = "CostSurface"
		self.tools = [Costsurf]


class Costsurf(object):
	def __init__(self):
		"""Derives cost surface model from four factors  with weighted criteria to calculate distance analysis between points."""
		self.category = 'Distance Analysis'
		self.name = 'Cost_Surface',
		self.label = 'Cost Surface'
		self.alias = 'Cost Surface',
		self.description = 'Compiles weighted criteria into a cost surface using a DEM, Landcover/Landuse, and road network data.'
		self.canRunInBackground = False

	def getParameterInfo(self):
		pdata = [
			['Terrain Dataset', 'dem', ['DERasterDataset', 'GPRasterLayer'], 'Required', 'Input', None, False],
			['Landcover Dataset', 'lulc', ['DERasterDataset', 'GPRasterLayer'], 'Required', 'Input', None, False],
			['Roads Dataset', 'road_vector', ['DEFeatureClass', 'GPFeatureLayer'], 'Required', 'Input', None, False],
			['River Dataset', 'river_vector', ['DEFeatureClass', 'GPFeatureLayer'], 'Required', 'Input', None, False],
			['Cost Type', 'platforms', 'GPString', 'Required', 'Input', None, True],
			['Processing area', 'processing_area', 'GPString', 'Required', 'Input', None, False],
			['Cell Size (Meters)', 'cell', 'GPString', 'Optional', 'Input', None, False]
		]

		"""Define parameter definitions"""
		params = [
			arcpy.Parameter(
				displayName=d[0],
				name=d[1],
				datatype=d[2],
				parameterType=d[3],
				direction=d[4],
				category=d[5],
				multiValue=d[6]) for d in [p for p in pdata]]

		params[4].filter.type = 'ValueList'
		# This way you can just add new platforms and their processing settings in
		# hlz_config.json and the script tool will automatically pick them up:
		params[4].filter.list = (list(PLATFORMS.keys()))

		params[5].filter.type = 'ValueList'
		params[5].filter.list = ['View Extent', 'Terrain coverage extent']
		params[5].value = 'View Extent'
		params[6].filter.type = 'ValueList'
		params[6].filter.list = ['5', '10']
		params[6].value = '5'

		return params

	def isLicensed(self):
		return True

	def updateParameters(self, parameters):
		return True

	def updateMessages(self, parameters):
		"""
		The first validation checks if the user's input data is projected. Then
		the deeper check inspects whether the input projections match, using the
		terrain source as the reference projection.
		"""
		epsg = None
		for idx, p in enumerate(parameters):
			if p.altered:
				if p.valueAsText and p.datatype in ['DERasterDataset', 'GPRasterLayer']:
					sr = arcpy.Describe(p.valueAsText).spatialReference
					if sr.type == 'Geographic':
						p.setErrorMessage('Input data must be projected.')
					else:
						if idx == 0:
							epsg = sr.factoryCode
						if epsg:
							if sr.factoryCode != epsg:
								p.setErrorMessage('Input data does not match terrain input projection.')
		return True

	def get_view_extent(self, sr):
		p = arcpy.mp.ArcGISProject("CURRENT")
		return p.activeView.camera.getExtent().projectAs(sr)

	def execute(self, parameters, messages):
		arcpy.env.overwriteOutput = True

		p = arcpy.mp.ArcGISProject('CURRENT')
		db = p.defaultGeodatabase
		m = p.activeMap
		ws = arcpy.env.workspace
		arcpy.env.cellSize = parameters[6].value

		dem = parameters[0].valueAsText
		lc = parameters[1].valueAsText
		rd_v = parameters[2].valueAsText
		rv_v = parameters[3].valueAsText
		platforms = parameters[4].values
		proc_area = parameters[5].valueAsText
		if proc_area == 'View Extent':
			arcpy.env.extent = self.get_view_extent(
				sr=arcpy.Describe(dem).spatialReference
			)
		else:
			arcpy.env.extent = dem
		cellsize = (f'{parameters[6].valueAsText} Meters')

		Delete("memory") # Clear Data stored in memory

		# Prep data for Cost Surface
		# Create Slope From DEM
		arcpy.AddMessage("Prepping Data For Cost Surface...")
		arcpy.AddMessage("\tSlope Prep...")
		Slope = SurfaceParameters(dem, 'SLOPE', 'QUADRATIC', cellsize, 'FIXED_NEIGHBORHOOD', 'METER', 'DEGREE')
		Slope.save('Slope')

		# Prep LULC
		arcpy.AddMessage("\tLandcover Prep...")
		extract = ExtractByMask(lc, rv_v, 'OUTSIDE', arcpy.env.extent) # Mask River vectors on LULC to enrich data
		lulc = Reclassify(extract, 'Value', "1 1;1 2 2;2 4 4;4 5 5;5 7 7;7 8 8;8 9 9;9 10 10;10 11 11;NODATA 1",
						  "DATA") # Reclass NODATA with value of 1 to fill in missing river cells
		lulc.save("lulc_prep")

		# Prep Road Data
		if 'River Cost' in platforms:
			arcpy.AddMessage("\tRoad Euclidean Distance Prep...")
			road_ED = DistanceAccumulation(rd_v, vertical_factor="BINARY 1 -30 30", horizontal_factor="BINARY 1 45", distance_method="GEODESIC")
		if 'Road Cost' in platforms or 'Foot Cost' in platforms:
			arcpy.AddMessage("\tRoad Raster Prep...")
			road_ras = FeatureToRaster(rd_v, 'OBJECTID', 'Road_ras', parameters[6].value)

		# Prep River Data
		arcpy.AddMessage("\tRiver Data Prep...")
		stream_ED = DistanceAccumulation(rv_v, vertical_factor="BINARY 1 -30 30", horizontal_factor="BINARY 1 45", distance_method="GEODESIC")

		# Reclassify Criteria with weights depending on Cost Type
		arcpy.AddMessage("Weighting Criteria for Cost Surface...")
		for plt in platforms:
			arcpy.AddMessage(f"Cost Surface: {plt}")
# 			arcpy.AddMessage("RECLASS VALUES FOR PLATFORM")
# 			arcpy.AddMessage(f"{PLATFORMS[plt]['slope']}")
# 			print(type(PLATFORMS[plt]["slope"]))
# 			try:
# 				rm = RemapRange(PLATFORMS[plt]["slope"])
# 				arcpy.AddMessage(rm)
# 				arcpy.AddMessage(type(rm))
# 			except Exception as e:
# 				arcpy.AddMessage("CAUGHT EXCEPTION!")
# 				arcpy.AddMessage(e)
# 				raise Exception

			# Slope Factor Reclass
			arcpy.AddMessage("\tWeighing Slope Factor...")
			Slope_Fact = Reclassify(
				Slope,
				"Value",
				RemapRange(PLATFORMS[plt]["slope"]),
				"NODATA"
			)

			# LULC Factor Reclass
			arcpy.AddMessage("\tWeighing Land Factor...")
			Land_Fact = Reclassify(
				lulc,
				"Value",
				RemapRange(PLATFORMS[plt]["lulc"]),
				"NODATA"
			)

			# River Factor Reclass
			arcpy.AddMessage("\tWeighing Stream Factor...")
			Stream_Fact = Reclassify(
				stream_ED,
				"Value",
				RemapRange(PLATFORMS[plt]["river_map"]),
				"NODATA"
			)

			# Road Factor Reclass
			arcpy.AddMessage("\tWeighing Road Factor...")
			if plt == "River Cost":
				dataset_r = road_ED
				data = "NODATA"
			else:
				dataset_r = road_ras
				data = "DATA"
			Road_Fact = Reclassify(
				dataset_r,
				"Value",
				RemapRange(PLATFORMS[plt]["road_map"]),
				data
			)

			arcpy.AddMessage("\tCreating Cost Surface...")
			Cost1 = Plus(Slope_Fact, Land_Fact)
			Cost2 = Plus(Road_Fact, Stream_Fact)
			CostSurface = Plus(Cost1, Cost2)
			name = os.path.join(ws, PLATFORMS[plt]["Cost_Name"])
			CostSurface.save(name)
			m.addDataFromPath(CostSurface)

		arcpy.AddMessage("Cost Surface Tool Complete!!!")