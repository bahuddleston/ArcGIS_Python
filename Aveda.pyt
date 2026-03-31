""" Aquatic Vector Extraction & Detection Application (AVEDA) v1.0
Separates and detects surface water from multispectral imagery.

AVEDA utilizes multispectral satellite imagery and derived Normalized
Difference Water Index (NDWI) datasets to identify and monitor changes in
surface water extent over time.

Input imagery is processed to extract the green and near-infrared (NIR) bands,
which are used to compute NDWI values for each scene. NDWI polygons are generated
to delineate water bodies and are temporally sorted by acquisition date to distinguish
pre- and post-event conditions. A change detection routine compares the earliest and
latest NDWI datasets to identify areas of water expansion or reduction.

Optional masking and field filtering steps refine the output, while symbology is applied
automatically to classify “Pre-Change,” “No Change,” and “Post-Change” zones for intuitive
visualization and analysis within ArcGIS Pro.

@Author: Bryan Huddleston
@Date: October 2025
@Credit: Bryan Huddleston
@Links:
"""

import arcpy, json, re, os
from datetime import datetime
from arcpy.conversion import *
from arcpy.sa import *
from arcpy.management import *
from arcpy.analysis import *
from osgeo import gdal

# Globals
def get_config():
	cfg_file = os.path.join(os.path.dirname(__file__), 'scripts', 'cfg', 'imagerybands.json')
	with open(cfg_file) as data:
		cfg = json.load(data)
		return cfg

CFG = get_config()
PLATFORMS = CFG["platforms"]
INDEX = CFG["index"]

class Toolbox(object):
	def __init__(self):
		self.label = "Toolbox"
		self.alias = "AVEDA"
		self.tools = [AVEDA]


class AVEDA(object):
	def __init__(self):
		"""Uses Bands in satellite imagery to extract water surfaces """
		self.category = 'Analysis'
		self.name = 'AVEDA',
		self.label = 'AVEDA'
		self.alias = 'AVEDA',
		self.description = "'Separates multiband imagery to obtain water surface information.'\
					'can detect change between two image rasters to identify increase/decrease in water surface.'"
		self.canRunInBackground = False

	def getParameterInfo(self):
		pdata = [
			['Input Image', 'in_image', 'DERasterDataset', 'Required', 'Input', None, True],
			['Image Type', 'i_type', 'GPString', 'Optional', 'Input', None, False],
			['Change Detection', 'cd', 'GPBoolean', 'Optional', 'Input', None, False],
			['Polygon Output', 'pcd', 'GPBoolean', 'Optional', 'Input', "Change Detection Options", False],
			['Raster Output', 'rcd', 'GPBoolean', 'Optional', 'Input', "Change Detection Options", False]

		]

		params = [
			arcpy.Parameter(
				displayName=d[0],
				name=d[1],
				datatype=d[2],
				parameterType=d[3],
				direction=d[4],
				category=d[5],
				multiValue=d[6]) for d in [p for p in pdata]]
		params[1].filter.type = "ValueList"
		params[1].filter.list = ["Airbus SPOT", "Planetscope", "Satellogic", "Vision-1", "WorldView-2 (4-Band)", "WorldView-2 (8-Band)", "WorldView-3"]
# 		params[1].value = "3 Band Image"

		return params

	def isLicensed(self):
		return True

	def updateParameters(self, parameters):
		if parameters[2].altered and parameters[2].value: # activates cd options if cd checked
			parameters[3].enabled = True
			parameters[4].enabled = True
		else:
			parameters[3].enabled = False
			parameters[3].value = None  # Clear if disabled
			parameters[4].enabled = False
			parameters[4].value = None  # Clear if disabled

		return True

	def updateMessages(self, parameters):
		return True

	def extract_date_from_filename(self, filename):
		# Common date formats in vendor imagery
		patterns = [
			(r'(\d{8})', "%Y%m%d"),               # 20251022
			(r'(\d{2}[A-Z]{3}\d{2})', "%y%b%d"),  # 25OCT22
			(r'(\d{4}_\d{2}_\d{2})', "%Y_%m_%d"), # 2025_10_22
			(r'(\d{2}-[A-Z]{3}-\d{2})', "%d-%b-%y"), # 22-OCT-25
		]

		for pattern, fmt in patterns:
			match = re.search(pattern, filename.upper())  # Upper() helps month abbreviations
			if match:
				date_str = match.group(1)
				try:
					dtg = datetime.strptime(date_str, fmt).strftime("%Y%m%d")
					return dtg
				except ValueError:
					continue
		return "unknown"

	def execute(self, parameters, messages):
		arcpy.env.overwriteOutput = True

		arcpy.SetLogMetadata(False)
		arcpy.SetLogHistory(False)

		in_image = parameters[0].valueAsText.split(';')
		i_type = parameters[1].valueAsText
		cd = parameters[2].value
		poly_cd = parameters[3].value
		ras_cd = parameters[4].value

		p = arcpy.mp.ArcGISProject('CURRENT')
		db = p.defaultGeodatabase
		m = p.activeMap
		ws = arcpy.env.workspace

		#Extract Bands From Raster
		ndwi_list = []
		poly_list = []
		date_list = []
		arcpy.AddMessage(f"***Lets Extract Water from Imagery***  (・_・ヾ")
		for idx, i in enumerate(in_image):
# 			try: # test to look for vendor name in image metadata
# 				img = gdal.Open(i)
# 				if img is None:
# 					arcpy.AddMessage("Could not open image: {}".format(i))
# 					continue
#
# 				metadata = img.GetMetadata()
# 				if not metadata:
# 					arcpy.AddMessage("No metadata found for {}".format(i))
# 					continue
#
# 				arcpy.AddMessage("Metadata for {}:".format(os.path.basename(i)))
# 				for k in list(metadata.keys()):
# 					v = metadata[k]
# 					arcpy.AddMessage("    {}: {}".format(k, v))
#
# 			except Exception as e:
# 				arcpy.AddWarning("Failed to read metadata for {}: {}".format(i, e))

			show_msg = idx == 0 # Show message in first iteration only

			#Extract DTG from image string for naming convention
			dtg = self.extract_date_from_filename(os.path.basename(i))
			date_list.append(dtg)
			arcpy.AddMessage(f"***Extracting Bands from {dtg} image...***")

			# --- Extract Bands from Imagery ---
			blue = Raster(f"{i}\\Band_{PLATFORMS[i_type]['blue']}")
			green = Raster(f"{i}\\Band_{PLATFORMS[i_type]['green']}")
			red = Raster(f"{i}\\Band_{PLATFORMS[i_type]['red']}")
			if i_type == "3 Band Image":
				pass
			else:
				nir = Raster(f"{i}\\Band_{PLATFORMS[i_type]['nir']}")

			if show_msg:
				arcpy.AddMessage(f"\t{i_type} Bands: \n\t\tBlue Band = {PLATFORMS[i_type]['blue']} \
					\n\t\tGreen Band = {PLATFORMS[i_type]['green']} \
					\n\t\tRed Band = {PLATFORMS[i_type]['red']}")
				if i_type == "3 Band Image":
					pass
				else:
					arcpy.AddMessage(f"\n\t\tNIR Band = {PLATFORMS[i_type]['nir']}")

# 			if i_type == "3 Band Image":  Output is not accurate enough for water extraction
# 				ndwi = Float(green - red) / Float(green + red)
# 				ExG = (2 * green) - red - blue
# 				Brightness = (red + green + blue) / 3
# 				ndwi_name = f"ndwi_{dtg}"
# 				ndwi.save(ndwi_name)
# 				ndwi_list.append(ndwi_name)
# 				ExG.save("ExG")
# 				Brightness.save("Brightness")
# 				# Combine conditions
# 				# Water = high VWI, low vegetation, low brightness (exclude shadows separately if needed)
# 				water_mask = Con((ndwi > 0.01) & (ExG < 0) & (Brightness <= 0) & (Brightness >= 20), 1, 0)
# 				water_mask.save(f"water_mask_{dtg}")
# 			else:
			ndwi = Float(green - nir) / Float(green + nir) # Water Extract
			ndwi_name = f"ndwi_{dtg}"
			ndwi.save(ndwi_name)
# 			ndti = (red - green) / (red + green) # Turbid Extract (Sediment Water)
# 			ndti.save(f"ndti_{dtg}")
			ndwi_list.append(ndwi_name)

			# --- Threshold NDWI to make binary mask ---
			# Adjust threshold as needed: typical range 0.0–0.1
			arcpy.AddMessage(f"\tThreshold NDWI to make binary mask...")
			threshold = 0.000000
			water_mask = Con(ndwi > threshold, 1, 0)
			water_mask.save(f"water_mask_{dtg}")

			arcpy.AddMessage(f"\tConverting Raster to Polygons...")
			name = f"ndwi_{dtg}_poly"
			w_poly = RasterToPolygon(water_mask, name, "SIMPLIFY", "", "SINGLE_OUTER_PART")
			sel = SelectLayerByAttribute(w_poly, where_clause="gridcode = 0")
			DeleteRows(sel)
			poly_list.append(w_poly)

			if not cd:
				m.addDataFromPath(ndwi)
				m.addDataFromPath(water_mask)
				m.addDataFromPath(w_poly)
			if len(in_image) <= 1:
				break

		arcpy.AddMessage("***Water Extraction Complete***   (و ˃̵ᴗ˂̵)و")

		if cd:
			arcpy.AddMessage(f"***Processing Change Detection***  ( ¬_¬)")
			sort_l = sorted(date_list) #sort imagery dates

			if poly_cd:
				arcpy.AddMessage(f"***Processing Polygon Change Detection...***")
				# Normalize all poly_list entries to strings (paths)
				ndwi_paths = []
				for fc in poly_list:
					if isinstance(fc, arcpy.Result):
						fc = fc.getOutput(0)
					ndwi_paths.append(fc)
				arcpy.AddMessage(f"\tCreating constant for NDWI...")
				# Create constant intersect polygon
				const = PairwiseIntersect(ndwi_paths, "memory\\ndwi_constant").getOutput(0)

				# Triage for new detect, no change, less change
				arcpy.AddMessage(f"\tData Triage for Change Detection...")
				fields = [f.name for f in arcpy.ListFields(const)] # List all field names
				drop_indexes = [2, 3, 5, 6, 7] # Define indexes to delete (0-based indexing)
				delete_fields = [fields[i] for i in drop_indexes if i < len(fields)] # Filter only valid indices
				if delete_fields:
					DeleteField(const, delete_fields)
				# Change constant gridcode to 0 for "no change"
				with arcpy.da.UpdateCursor(const, ["gridcode"]) as cursor:
					for row in cursor:
						if row[0] == 1:
							row[0] = 0
							cursor.updateRow(row)

				# Get the earliest date
				earliest_date = sort_l[0]
				# Find earliest FC and flip its gridcode from 1 → -1 (not present detections)
				earliest_fc = None
				for fc in ndwi_paths:
					fc_name = os.path.basename(fc)
					if str(earliest_date) in fc_name:
						earliest_fc = fc
						with arcpy.da.UpdateCursor(earliest_fc, ["gridcode"]) as cursor:
							for row in cursor:
								if row[0] == 1:
									row[0] = -1
									cursor.updateRow(row)
						arcpy.AddMessage(f"\t\tPre water levels= 1 → -1 \
							\n\t\tConstant water levels= 1 → 0 \
							\n\t\tPost water levels = 1")
						break

				# Erase all polygons against the constant
				arcpy.AddMessage(f"\tPerforming Pairwise Erase for change detection features...")
				c_list = []
				c_list.append(const)
				for l in ndwi_paths:
					l_name = os.path.basename(l).replace("poly", "change")
					out_name = os.path.join("memory", l_name)
					erase_result = PairwiseErase(l, const, out_name).getOutput(0)
					c_list.append(erase_result)

				arcpy.AddMessage(f"\tMerging change polygons...")
				cd_out = Merge(c_list, "ndwi_CDetect")
				cd_lyr = m.addDataFromPath(cd_out)


				# ---Apply Polygon Symbology---
				sym = cd_lyr.symbology
				sym.updateRenderer('UniqueValueRenderer')
				sym.renderer.fields = ['gridcode']
				for grp in sym.renderer.groups:
					for itm in grp.items:
						try:
							val = int(itm.values[0][0])
							arcpy.AddMessage(f"Values: {val}")
						except:
							arcpy.AddMessage(f"Values: None")
							continue
						# Outline style for all
						itm.symbol.outlineColor = {'RGB': [0, 0, 0, 0]}
						itm.symbol.outlineWidth = 0.5
						# Color and label mapping
						if val == -1:
							itm.symbol.color = {'RGB': [168, 0, 0, 75]}  # Tuscan Red
							itm.label = 'Water Loss'
						elif val == 0:
							itm.symbol.color = {'RGB': [189, 190, 190, 75]}  # Transparent white (No Change)
							itm.label = 'No Change'
						elif val == 1:
							itm.symbol.color = {'RGB': [0, 112, 255, 75]}  # Azure Blue
							itm.label = 'Water Gain'
				cd_lyr.symbology = sym

			if ras_cd:
				arcpy.AddMessage("***Processing Rasters for Change Detection***...")
				fc_paths = []
				for fc in ndwi_list:
					if isinstance(fc, arcpy.Result):
						fc_paths.append(fc.getOutput(0))
					else:
						fc_paths.append(fc)

				pre_fc = next((fc for fc in ndwi_list if sort_l[0] in fc), None)
				post_fc = next((fc for fc in ndwi_list if sort_l[-1] in fc), None)

				if pre_fc is None or post_fc is None:
					arcpy.AddError(f"(╥_╥) Could not find matching NDWI rasters for dates: {sort_l[0]}, {sort_l[-1]} (╥_╥)")
				else:
					arcpy.AddMessage("Processing Rasters for Change Detection...")
					change = Raster(post_fc) - Raster(pre_fc)
					change.save("ndwi_changeD")
					ras_lyr = m.addDataFromPath(change)

				lyr = ras_lyr
				lyr.name = arcpy.Describe(ras_lyr).name
				sym = lyr.symbology
				sym.updateColorizer('RasterStretchColorizer')
				sym.colorizer.classificationMethod = 'StandardDeviation'
				sym.colorizer.colorRamp = p.listColorRamps('Red-Blue (Continuous)')[0]
				sym.colorizer.noDataColor = {'RGB': [0, 0, 0, 0]}
				sym.colorizer.minLabel = "Water Loss"
				sym.colorizer.maxLabel = "Water Gain"
				lyr.symbology = sym
				lyr.transparency = 20

			arcpy.AddMessage("AVEDA Tool Complete...  (┛ಠ_ಠ)┛彡┻━┻")