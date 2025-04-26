"""HLZ Suitability

This module takes as input a DEM (surface model or bare earth), a landcover
raster (optional), vertical obstructions (optional) and landing zone candidates
as a Point layer (optional).

LULC Source is Sentinel-2 Data from Esri's Living Atlas:
https://livingatlas.arcgis.com/landcoverexplorer/

Obstruction Options should be used if a defined DSM is not available for analysis.

The user selects a helicopter platform and the data is analyzed and reclassified
to show possible landing zone candidates.

HLZ Suitability v2.0 (04/22/2025):
- Added method to ingest horizontal obstructions (power lines, rivers, etc.) to further enrich data.
- Updated Reclass values for Esri Sentinel-2 Data
- symbology labeling is still a bug (Esri is tracking)
- Replaced Combine with Mosaic to New Raster to maintain Max values for enhanced rasters
- Added Function to process Pass Zone Rectangles and assess zone capacity

@Author: Bryan Huddleston
@Date: October 2023
@Credit: Bryan Huddleston, Eric Eagle
@Links:
"""

import arcpy, os, sys, math, json
from arcpy.sa import *
from arcpy.management import *
from arcpy.conversion import *
from arcpy.analysis import *
import networkx as nx


# Globals
def get_config():
	cfg_file = os.path.join(os.path.dirname(__file__), 'scripts', 'cfg', 'hlz_config.json')
	with open(cfg_file) as data:
		cfg = json.load(data)
		return cfg

CFG = get_config()
PLATFORMS = CFG["platforms"]
REMAPS = CFG["remaps"]

sys.dont_write_bytecode = True
class Toolbox(object):
	def __init__(self):
		self.label = "Toolbox"
		self.alias = "Suitability"
		self.tools = [HLZsuit]


class HLZsuit(object):
	def __init__(self):
		"""Creates slope from DSM or DEM for suitable helicopter landing zones within a study area."""
		self.category = 'Analysis'
		self.name = 'HLZSuitabilityAnalysis',
		self.label = 'HLZ Suitability Analysis'
		self.alias = 'HLZ Suitability Analysis',
		self.description = 'Identifies suitable areas for helicopter landing operations'
		self.canRunInBackground = False

	def getParameterInfo(self):
		pdata = [
			['Terrain Dataset (DSM)', 'terrain_dem', ['DERasterDataset', 'GPRasterLayer'], 'Required', 'Input', None, False],
			['Platform', 'platform', 'GPString', 'Required', 'Input', None, True],
			['Landcover Data', 'lulc', ['DERasterDataset', 'GPRasterLayer'], 'Optional', 'Input', 'Obstruction Options', False],
			['Horizontal Obstructions', 'hori_obs', ['DEFeatureClass', 'GPFeatureLayer'], 'Optional', 'Input', 'Obstruction Options', False],
			['Vertical Obstructions', 'vert_obs', ['DEFeatureClass', 'GPFeatureLayer'], 'Optional', 'Input', 'Obstruction Options', False],
			['HLZ Points (Pre-Selected)', 'hlz', ['DEFeatureClass', 'GPFeatureLayer'], 'Optional', 'Input', None, False],
			['Processing area', 'processing_area', 'GPString', 'Required', 'Input', None, False],
			['Cell Size', 'cell', 'GPString', 'Optional', 'Input', None, False],
			['Estimate HLZ Capacity', 'cap', 'GPBoolean', 'Optional', 'Input', None, False]
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

		params[1].filter.type = 'ValueList'
		# This way you can just add new platforms and their processing settings in
		# hlz_config.json and the script tool will automatically pick them up:
		params[1].filter.list = (list(PLATFORMS.keys()))

		params[6].filter.type = 'ValueList'
		params[6].filter.list = ['View Extent', 'Terrain coverage extent']
		params[6].value = 'View Extent'
		params[7].value = 10

		return params

	def isLicensed(self):
		return True

	def updateParameters(self, parameters):
# 		platform_param = parameters[1]
# 		obstruction_params = parameters[2:5]  # lulc, r_obs, vert_obs
#
# 		# Check if any obstruction layers are set
# 		obstruction_used = any(p.altered and p.valueAsText for p in obstruction_params)
# 		if obstruction_used:
# 			# If any obstruction data is supplied, keep only the selected platform in the list
# 			selected = platform_param.valueAsText
# 			if selected in PLATFORMS.keys():
# 				platform_param.filter.list = [selected]
# 			else:
# 				platform_param.filter.list = []
# 		else:  # Otherwise, show all platforms
# 			platform_param.filter.list = list(PLATFORMS.keys())
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

	def generate_hlz_capacity(self, polygon_fc, fail, clearance_m, output_fc, spatial_ref, ws):
		"""
		For each polygon, fills it with non-overlapping circular buffers representing aircraft capacity.
		Then cleans Clearance Buffers if they intersect with fail features to output a clean hlz polygons.
		"""

		arcpy.env.outputCoordinateSystem = spatial_ref
		arcpy.env.overwriteOutput = True

		buffer_gap = 0.5  # meters between circles
		diameter = float(clearance_m) * 2
		grid_spacing = diameter + buffer_gap  # ensures no touching
		temp_points = os.path.join("memory", "hlz_grid_points")
		label_points = temp_points + "_label"
		selected_points = os.path.join("memory", "hlz_selected_points")
		safe_output_name = output_fc.replace("-", "_").replace(" ", "_")
		raw_circles = os.path.join(ws, safe_output_name)

		extent = arcpy.Describe(polygon_fc).extent
		xmin, ymin, xmax, ymax = extent.XMin, extent.YMin, extent.XMax, extent.YMax

		CreateFishnet(
			out_feature_class=temp_points,
			origin_coord=f"{xmin} {ymin}",
			y_axis_coord=f"{xmin} {ymin + 1}",
			cell_width=grid_spacing,
			cell_height=grid_spacing,
			number_rows="",
			number_columns="",
			labels="LABELS",
			template=polygon_fc,
			geometry_type="POLYLINE"  # must be POLYLINE for ArcGIS to accept
		)

		SpatialJoin(
			target_features=label_points,
			join_features=polygon_fc,
			out_feature_class=selected_points,
			join_type="KEEP_COMMON"
		)

		Buffer(
			in_features=selected_points,
			out_feature_class=raw_circles,
			buffer_distance_or_field=f"{clearance_m} Meters",
			line_side="FULL",
			line_end_type="ROUND",
			dissolve_option="NONE"
		)

		sel = SelectLayerByLocation(raw_circles, "INTERSECT", fail, "", "NEW_SELECTION", "INVERT")
		hlz_clearance = raw_circles.replace("_raw", "")
		CopyFeatures(sel, hlz_clearance)

		# Clean up any previous runs
		for fc in [temp_points, polygon_fc, fail, label_points, selected_points, raw_circles]:
			if arcpy.Exists(fc):
				Delete(fc)

		return hlz_clearance

	def generate_hlz_zones(self, hlz_clearance, ws):
		arcpy.AddMessage('\tCreating Tentative HLZ Areas...')
		# Generate Near Table
		near_table = os.path.join("memory", "near_table")
		arcpy.analysis.GenerateNearTable(
			in_features=hlz_clearance,
			near_features=hlz_clearance,
			out_table=near_table,
			search_radius="10 Meters",
			location="NO_LOCATION",
			angle="NO_ANGLE",
			closest="ALL"
		)

		# Build proximity graph
		G = nx.Graph()
		with arcpy.da.SearchCursor(near_table, ["IN_FID", "NEAR_FID"]) as cursor:
			for in_fid, near_fid in cursor:
				if in_fid != near_fid:
					G.add_edge(in_fid, near_fid)

		# Assign group IDs to each component
		group_map = {}
		for group_id, component in enumerate(nx.connected_components(G), start=1):
			for fid in component:
				group_map[fid] = group_id

		# Add group ID to HLZ circles
		temp_fc = os.path.join("memory", "hlz_with_group")
		CopyFeatures(hlz_clearance, temp_fc)
		AddField(temp_fc, "GroupID", "LONG")

		with arcpy.da.UpdateCursor(temp_fc, ["OID@", "GroupID"]) as cursor:
			for row in cursor:
				oid = row[0]
				row[1] = group_map.get(oid, -1)
				cursor.updateRow(row)

		# Dissolve by GroupID
		dissolved = os.path.join("memory", "hlz_dissolved_groups")
		Dissolve(temp_fc, dissolved, "GroupID")

		# Generate bounding rectangles
		hlz_zones = os.path.join(ws, f"{hlz_clearance.replace('_capacity','_zones')}")
		MinimumBoundingGeometry(
        in_features=dissolved,
        out_feature_class=hlz_zones,
        geometry_type="RECTANGLE_BY_AREA",
        group_option="LIST",
        group_field="GroupID"
    )

		sel_a = SelectLayerByAttribute(hlz_zones, 'NEW_SELECTION', '"Shape_Length" > 2000')
		DeleteRows(sel_a) # Delete Unnecessarily Large HLZ Areas

		# Clean up any previous runs
		for fc in [temp_fc, dissolved]:
			if arcpy.Exists(fc):
				Delete(fc)

		return hlz_zones

	def execute(self, parameters, messages):
		arcpy.env.overwriteOutput = True

		p = arcpy.mp.ArcGISProject('CURRENT')
		db = p.defaultGeodatabase
		m = p.activeMap
		ws = arcpy.env.workspace

		dem = parameters[0].valueAsText
		plts = parameters[1].values
		lulc = parameters[2].valueAsText
		hori = parameters[3].valueAsText
		vert = parameters[4].valueAsText
		points = parameters[5].valueAsText
		arcpy.env.cellSize = parameters[7].valueAsText
		cell = arcpy.env.cellSize
		cap = parameters[8].value

		proc_area = parameters[6].valueAsText
		if proc_area == 'View Extent':
			arcpy.env.extent = self.get_view_extent(
				sr=arcpy.Describe(dem).spatialReference
			)
		else:
			arcpy.env.extent = dem

		# Process Slope
		arcpy.SetProgressor('default', 'Calculating Slope...')
		slope_hlz = SurfaceParameters(
			in_raster=dem,
			parameter_type='SLOPE',
			output_slope_measurement='DEGREE')
		arcpy.AddMessage('Created slope...')

		# Storing outputs in a dictionary makes it easier to do
		# conditional processing later
		rasters = {
			"slopes": [],
			"optional": {
				"land_cover": None,
				"vertical_obstructions": None
			}
		}

		for plt in plts:
			arcpy.AddMessage(f"PLATFORM: {plt}")
			arcpy.AddMessage("\tRECLASS VALUES FOR PLATFORM")
			arcpy.AddMessage(f'\t{PLATFORMS[plt]["reclass"]}')

			reclassed_slope = Reclassify(slope_hlz, "VALUE", RemapRange(PLATFORMS[plt]["reclass"]), "NODATA")
			reclassed_slope.save(PLATFORMS[plt]["shortname"])
			rasters['slopes'].append(reclassed_slope)

		if lulc: # Reclass LULC for enhanced obstruction raster
			arcpy.SetProgressor('default', 'Adding landcover data...')
			arcpy.AddMessage('Adding landcover data.')
# 			if river: # Reclass NODATA with value of 1 to fill in missing river cells
# 				extract = ExtractByMask(lulc, river, 'OUTSIDE', arcpy.env.extent)  # Mask River vectors on LULC to enrich data
# 				lulc_e = Reclassify(extract, 'Value', RemapValue(REMAPS["water"]), "DATA")
# 			else:
# 				lulc_e = lulc
			land_fact = Reclassify(lulc, 'VALUE', RemapValue(REMAPS["lulc"]), 'NODATA')
			land_fact.save("HLZ_LULC")
			rasters['optional']['land_cover'] = land_fact

		if hori:
			arcpy.SetProgressor('default', 'Adding horizontal obstructions...')
			arcpy.AddMessage('Adding horizontal obstructions.')
			hori_ras = FeatureToRaster(hori, 'OBJECTID', 'memory\hori_ras', cell)
			hori_obs = Reclassify(hori_ras, 'VALUE', RemapRange(REMAPS["obs"]))
			hori_obs.save("Hori_Obs")
			rasters['optional']['horizontal_obstructions'] = hori_obs

		if vert:
			arcpy.SetProgressor('default', 'Adding vertical obstructions...')
			arcpy.AddMessage('Adding vertical obstructions.')
			vert_ras = FeatureToRaster(vert, 'OBJECTID', 'memory\obs_ras', cell)
			vert_obs = Reclassify(vert_ras, 'VALUE', RemapRange(REMAPS["obs"]))
			vert_obs.save("Vert_Obs")
			rasters['optional']['vertical_obstructions'] = vert_obs

		options = rasters['optional']
		extras_list = [i for i in options.values() if i is not None]
		field_list = [f'!{arcpy.Describe(v).name}!' for v in options.values() if v is not None]
		outputs = []
		combos = []
		if extras_list:
			for slope in rasters['slopes']:
				combine_inputs = [slope] + extras_list
				name = os.path.basename(str(slope))
				e_name = f'{name}_enhanced'
				hlz_combo = MosaicToNewRaster(combine_inputs, ws, e_name, "", "8_BIT_UNSIGNED", \
												cell, "1", "MAXIMUM", "FIRST")
				outputs.append(hlz_combo)
		else:
			outputs = rasters['slopes']

		cap_list = []
		# Symbolize HLZ Slope
		arcpy.SetProgressor('default', 'Applying symbology...')
		for i, o in enumerate(outputs):
			lyr = m.addDataFromPath(o)
			lyr.name = arcpy.Describe(o).name
			sym = lyr.symbology
			sym.updateColorizer('RasterClassifyColorizer')
			sym.colorizer.classificationMethod = 'ManualInterval'
			sym.colorizer.breakCount = 3
			sym.colorizer.colorRamp = p.listColorRamps('Slope')[0]
			sym.colorizer.noDataColor = {'RGB': [0, 0, 0, 0]}
			label_l = ['Pass', 'Fringe', 'Fail']
			count = 0
			for brk in sym.colorizer.classBreaks: # Current Esri Bug, wont label features
				brk.label = label_l[count]
				count +=1
			lyr.symbology = sym
			lyr.transparency = 40

			if cap:
				# Process Pass areas for HLZ Capacity
				arcpy.AddMessage("Estimating aircraft capacity per suitable zone...")
				plt = plts[i]  # Match raster to platform
				clearance = float(PLATFORMS[plt]["clearance"].split(" ")[0])
				min_area = 3.1416 * (float(clearance ** 2)) # Calculate sqm for Clearance Radius
				arcpy.AddMessage(f"\tMinimum area required per {plt}: {round(min_area)} m²")

				# Find Pass/Fail areas and Convert to polygons
				suitable = SetNull(o, 1, "VALUE <> 1") # Reclass to isolate only suitable ("pass") areas
				p_pass = os.path.join(ws, f"{plt.replace('-','_').split(' ')[0]}_pass")
				n_suitable = SetNull(o, 3, "VALUE <> 3") # Reclass to isolate only not suitable ("fail") areas
				p_fail = os.path.join(ws, f"{plt.replace('-','_').split(' ')[0]}_fail")
				RasterToPolygon(suitable, p_pass, "NO_SIMPLIFY")
				RasterToPolygon(n_suitable, p_fail, "NO_SIMPLIFY")

				# Function to Identify HLZ Capacity
				hlz_circles_fc = self.generate_hlz_capacity(
					polygon_fc=p_pass,
					fail=p_fail,
					clearance_m=clearance,
					output_fc= os.path.join(ws, f"{plt.replace('-','_').split(' ')[0]}_capacity_raw"),
					spatial_ref=arcpy.Describe(p_pass).spatialReference,
					ws=ws
				)

				# Function to generate HLZ Areas
				zones = self.generate_hlz_zones(hlz_circles_fc, ws)

				cap_list.clear()  # Reset capacity list
				cap_list.append(hlz_circles_fc)
				cap_list.append(zones)

				# Symbology for capacity and zones
			if cap:
				for c in cap_list:
					clyr = m.addDataFromPath(c)
					clyr.name = arcpy.Describe(c).name
					arcpy.AddMessage(clyr.name)
					sym = clyr.symbology
					sym.updateRenderer('SimpleRenderer')
					if 'capacity' in clyr.name:
						sym.renderer.symbol.applySymbolFromGallery('Dashed Black Outline')
						sym.renderer.symbol.outlineWidth = 1.0
					else:
						sym.renderer.symbol.applySymbolFromGallery('Black Outline')
						sym.renderer.symbol.outlineColor = {'RGB': [85, 255, 0, 100]}  # Medium Apple (Green)
						sym.renderer.symbol.outlineWidth = 2.0
					clyr.symbology = sym

		if points:
			buff_list = []
			arcpy.SetProgressor('default', 'Buffering...')
			arcpy.AddMessage('Creating clearance radius for Pre Selected HLZ points...')
			for plt in plts:
				buff = arcpy.PairwiseBuffer_analysis(
					points,
					PLATFORMS[plt]["fc_name"],
					PLATFORMS[plt]["clearance"],
					method='PLANAR')
				lz = m.addDataFromPath(buff)
				buff_list.append(lz)

				arcpy.SetProgressor('default', 'Symbolizing buffers...')

				for l in buff_list:
					sym = l.symbology

					sym.updateRenderer('UniqueValueRenderer')
					sym.renderer.fields = ['BUFF_DIST']

					# Apply symbology from gallery
					for grp in sym.renderer.groups:
						for itm in grp.items:
							val = int(itm.values[0][0])
							if val in [25, 40]:
								itm.symbol.applySymbolFromGallery('Offset Hatch Border, No Fill')
								if val == 25:
									itm.label = '25m Radius'
								if val == 40:
									itm.label = '40m Radius'
					l.symbology = sym
		arcpy.AddMessage("HLZ Suitability Complete!!!   (┛ಠ_ಠ)┛彡┻━┻")
