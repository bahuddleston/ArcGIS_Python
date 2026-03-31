import arcpy, json, re, os, sys
import numpy as np
from arcpy.conversion import *
from arcpy.sa import *
from arcpy.management import *
from arcpy.analysis import *


class Toolbox(object):
	def __init__(self):
		self.label = "Toolbox"
		self.alias = "RoadHog"
		self.tools = [RoadHog]


class RoadHog(object):
	def __init__(self):
		"""Uses Bands in satellite imagery to extract water surfaces """
		self.category = 'Analysis'
		self.name = 'RoadHog',
		self.label = 'Road Hog'
		self.alias = 'Road Hog',
		self.description = "'Separates multiband imagery to obtain water surface information.'\
					'can detect change between two image rasters to identify increase/decrease in water levels.'"
		self.canRunInBackground = False

	def getParameterInfo(self):
		pdata = [
			['Vehicle Dataset', 'v_data', ['DEFeatureDataset', 'GPFeatureLayer'], 'Required', 'Input', None, False],
			['Road Dataset', 'r_data', ['DEFeatureDataset', 'GPFeatureLayer'], 'Required', 'Input', None, False],
			['Output Coordinate System', 'crs', 'GPCoordinateSystem', 'Optional', 'Input', None, False],
			['Search Radius (Meters)', 'b_dist', 'GPString', 'Optional', 'Input', 'Threshold Options', False],
			['Fixed Threshold', 'fixed', 'GPBoolean', 'Optional', 'Input', 'Threshold Options', False],
			['Percentage Threshold', 'p_bool', 'GPBoolean', 'Optional', 'Input', 'Threshold Options', False],
			['Density', 'd_bool', 'GPBoolean', 'Optional', 'Input', 'Threshold Options', False]

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
		params[3].value = 10
		params[4].value = True

		return params

	def isLicensed(self):
		return True

	def updateParameters(self, parameters):
# 		if parameters[3].altered and parameters[3].value:
# 			parameters[4].enabled = True
# 			parameters[5].enabled = True
# 			parameters[6].enabled = True
# 		else:
# 			parameters[4].enabled = False
# 			parameters[4].value = None  # Clear if disabled
# 			parameters[5].enabled = False
# 			parameters[5].value = None  # Clear if disabled
# 			parameters[6].enabled = False
# 			parameters[6].value = None  # Clear if disabled

		return True

	def updateMessages(self, parameters):
		return True

	def execute(self, parameters, messages):
		arcpy.env.overwriteOutput = True

		v_data = parameters[0].valueAsText # .split(';')
		r_data = parameters[1].valueAsText
		out_crs = parameters[2].valueAsText
		b_dist = parameters[3].value
		fixed = parameters[4].value
		p_bool = parameters[5].value
		d_bool = parameters[6].value

		p = arcpy.mp.ArcGISProject('CURRENT')
		db = p.defaultGeodatabase
		m = p.activeMap
		ws = arcpy.env.workspace

		if out_crs:
			arcpy.env.outputCoordinateSystem = out_crs
			arcpy.AddMessage(f"Environment CRS set to: {out_crs}")
		else:
			# Optional fallback: use current map’s CRS
			aprx = arcpy.mp.ArcGISProject("CURRENT")
			arcpy.env.outputCoordinateSystem = aprx.activeMap.spatialReference
			arcpy.AddMessage(f"No CRS specified. Defaulting to map CRS: {arcpy.env.outputCoordinateSystem.name}")

		base_name = os.path.basename(v_data)
		# Extract date in format YYYY-MM-DD from the start of the file name
		match = re.search(r"(\d{4}[-_]?\d{2}[-_]?\d{2})", base_name)
		
		if match:
			# Normalize to digits only (remove '-' or '_')
			date_tag = re.sub(r"[-_]", "", match.group(1))
		else:
			date_tag = "unknown_date"

		# --- Feature to Point ---
		arcpy.AddMessage("Ensuring vehicle dataset contains clean centroids...")
		desc_v = arcpy.Describe(v_data)
		if desc_v.shapeType.lower() == "polygon":
			arcpy.AddMessage("Converting vehicle polygon features to points...")
			v_points = FeatureToPoint(v_data, "memory/veh_points")
		else:
			arcpy.AddMessage("Point features detected...")
			v_points = v_data

		# --- Pairwise Buffer for Proximity ---
		arcpy.AddMessage("Processing Proximity Count Analysis...")
		arcpy.AddMessage("\tCreating 25-meter road buffer...")
		if b_dist:
			dist = str(b_dist) + " Meters"
		else:
			dist = "15 Meters"
		road_buffer = PairwiseBuffer(r_data, "memory/road_buffer", dist)

		# --- Spatial Join  ---
		arcpy.AddMessage("\tPerforming Spatial Join (count vehicles per buffer)...")
		join_result = SpatialJoin(
			target_features=road_buffer,
			join_features=v_points,
			out_feature_class="memory/road_vehicle_join",
			field_mapping="",
			join_operation="JOIN_ONE_TO_ONE",
			join_type="KEEP_ALL",
			match_option="INTERSECT"
		)

		# --- Join Field (attach Join_Count to roads) ---
		arcpy.AddMessage("\tJoining vehicle counts to road features...")
		JoinField(
			in_data=r_data,
			in_field="OBJECTID",
			join_table=join_result,
			join_field="TARGET_FID",
			fields=["Join_Count"]
		)

		# --- Add / classify traffic field ---
		arcpy.AddMessage("Classifying traffic levels...")
		field_name = "Traffic_Level"
		if field_name not in [f.name for f in arcpy.ListFields(r_data)]:
			AddField(r_data, field_name, "TEXT")

		counts = [row[0] for row in arcpy.da.SearchCursor(r_data, ["Join_Count"]) if row[0] is not None]
		if not counts:
			arcpy.AddWarning("No vehicle observations found near roads.")
			return

		if fixed:
			arcpy.AddMessage("\tClassifying roads by count number...")
			with arcpy.da.UpdateCursor(r_data, ["Join_Count", "Traffic_Level"]) as cursor:
				for row in cursor:
					count = row[0] if row[0] is not None else 0
					if count < 10:
						row[1] = "Low"
					elif count < 20:
						row[1] = "Moderate"
					else:
						row[1] = "High"
					cursor.updateRow(row)

		if p_bool:
			arcpy.AddMessage("\tClassifying roads by Percentage...")
			low_thresh = np.percentile(counts, 33)
			high_thresh = np.percentile(counts, 66)
			arcpy.AddMessage(f"\tClassifying data by thresholds...")
			with arcpy.da.UpdateCursor(r_data, ["Join_Count", field_name]) as cursor:
				for count, level in cursor:
					if count is None or count == 0:
						level = "Low"
					elif count <= low_thresh:
						level = "Low"
					elif count <= high_thresh:
						level = "Moderate"
					else:
						level = "High"
					cursor.updateRow((count, level))
			arcpy.AddMessage(f"\tThresholds → Low ≤ {low_thresh:.0f}, Moderate ≤ {high_thresh:.0f}, High > {high_thresh:.0f}")

		if d_bool:
			# --- Add and calculate density ---
			arcpy.AddMessage("Calculating vehicle density per road segment...")
			fields = [f.name for f in arcpy.ListFields(r_data)]
			if "Veh_Density" not in fields:
				AddField(r_data, "Veh_Density", "DOUBLE")
			if "Traffic_Level" not in fields:
				AddField(r_data, "Traffic_Level", "TEXT")

			with arcpy.da.UpdateCursor(r_data, ["Join_Count", "SHAPE@", "Veh_Density", "Traffic_Level"]) as cursor:
				for row in cursor:
					count = row[0] if row[0] is not None else 0
					length_m = row[1].getLength("PLANAR", "METERS")
					density = count / length_m if length_m > 0 else 0
					row[2] = density

					# Convert to vehicles per 15 m
					dens_15m = density * 15  # normalizing by 15m segment
					if dens_15m < 0.4:
						row[3] = "Low"        # roughly <1 vehicle per 150 m
					elif dens_15m < 1.0:
						row[3] = "Moderate"   # roughly 1 vehicle per 15–150 m
					else:
						row[3] = "High"       # ≥1 vehicle per 15 m

					cursor.updateRow(row)

		# --- Save Output & Symbolize ---
		arcpy.AddMessage("Saving output feature class...")
		out_file = f"road_density_{date_tag}"
		dense = CopyFeatures(r_data, out_file)
		final = m.addDataFromPath(dense)

		sym = final.symbology
		sym.updateRenderer('UniqueValueRenderer')
		sym.renderer.fields = ['Traffic_Level']

		# Define color mapping (RGB with alpha)
		color_map = {
			"High": {'RGB': [168, 0, 0, 100]},       # Red
			"Moderate": {'RGB': [191, 191, 0, 100]}, # Yellow
			"Low": {'RGB': [55, 165, 0, 100]}        # Green
		}

		# Loop through renderer items
		for grp in sym.renderer.groups:
			for itm in grp.items:
				val = itm.values[0][0]
				if val in color_map:
					itm.symbol.outlineWidth = 0.75
					itm.symbol.outlineColor = {'RGB': [0, 0, 0, 100]}  # black outline
					itm.symbol.color = color_map[val]
					itm.label = val  # clean label
					arcpy.AddMessage(f"Applied color for: {val}")
				else:
					arcpy.AddMessage(f"Skipped unknown value: {val}")
		final.symbology = sym

		arcpy.AddMessage(f"✅ Process complete! Output saved as: {out_file}")