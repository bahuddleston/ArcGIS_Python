import arcpy, os, sys
from arcpy.management import *
from arcpy.conversion import *
from arcpy import da
# import datetime.datetime as datetime


class Toolbox(object):
	def __init__(self):
		self.label = "Toolbox"
		self.alias = "AIS_Finder"
		self.tools = [AISFind]


class AISFind(object):
	def __init__(self):
		"""Uses .csv data to append new data to original vector data feature class."""
		self.category = 'Analysis'
		self.name = 'AIS_Finder',
		self.label = 'AIS Finder'
		self.alias = 'AIS Finder',
		self.description = "'Searches AIS dataset to create tracks of Ship # and class.'\
				   'Script also identifies anomolies such as spoofing, etc.'"
		self.canRunInBackground = False

	def getParameterInfo(self):
		pdata = [
# 			['Spreadsheet input', 'in_spread', ['DEFile', 'GPDataFile'], 'Optional', 'Input', None]
			['Point Feature input', 'in_spread', ['DEFeatureClass', 'GPFeatureLayer'], 'Optional', 'Input', None]
		]

		params = [
			arcpy.Parameter(
				displayName=d[0],
				name=d[1],
				datatype=d[2],
				parameterType=d[3],
				direction=d[4],
				category=d[5]) for d in [p for p in pdata]]
# 		params[2].value = True
# 		params[3].value = False
# 		params[10].value = True
# 		params[12].value = False
# 		params[13].filter.type = "ValueList"
# 		params[13].filter.list = ["Group 1", "Group 2", "Group 3"]
# 		params[13].value = "Group 1"

		return params

	def isLicensed(self):
		return True

	def updateParameters(self, parameters):
# 		if parameters[3].valueAsText == "true":
# 			for p in parameters[4:]:
# 				p.enabled = True
# 				if parameters[10].valueAsText == 'true':
# 					parameters[11].enabled = False
# 				if parameters[10].valueAsText == 'false':
# 					parameters[10].enabled = False
# 				if parameters[11].valueAsText == 'false':
# 					parameters[10].enabled = True
# 				if parameters[12].valueAsText == 'false':
# 					parameters[13].enabled = True
# 				else:
# 					parameters[13].enabled = True
# 		else:
# 			for p in parameters[4:]:
# 				p.enabled = False

		# Populate parameter values in fc metadata (must be completed in .gdb or metadata does NOT populate)
# 		if parameters[4]:
# 			meta = md.Metadata(parameters[1].valueAsText)
# 			parameters[4].value = meta.title
# 			parameters[5].value = meta.tags
# 			parameters[6].value = meta.summary
# 			parameters[7].value = meta.description
# 			parameters[8].value = meta.credits
# 			parameters[9].value = meta.accessConstraints

		return True

	def updateMessages(self, parameters):
		return True

	def get_home_path(self):
		p = arcpy.mp.ArcGISProject("CURRENT")
		return Path(p.homeFolder).resolve()

	def execute(self, parameters, messages):
		arcpy.env.overwriteOutput = True

		arcpy.SetLogMetadata(False)
		arcpy.SetLogHistory(False)

		ais_pts = parameters[0].valueAsText

		p = arcpy.mp.ArcGISProject('CURRENT')
		db = p.defaultGeodatabase
		m = p.activeMap
		ws = arcpy.env.workspace

		arcpy.AddMessage(f"\tReading AIS Feature Class...")

		# Extract all unique (mmsi, date) pairs
		arcpy.AddMessage(f"\tIndexing MMSI and timestamp values...")
		vessel_dates = set()
		with da.SearchCursor(ais_pts, ['mmsi', 'timestamp']) as cursor:
			for mmsi_val, ts in cursor:
				if ts:
					date_str = ts.date().isoformat()
					vessel_dates.add((mmsi_val, date_str))
		del cursor

		arcpy.AddMessage(f"\tFound {len(vessel_dates)} MMSI-date combinations...")

		# Generate lines per (mmsi, date)
		arcpy.AddMessage(f"\tGenerating daily vessel tracks...")
		p_list = []
		for count, (mmsi_val, date_str) in enumerate(sorted(vessel_dates), start=1):
			l_name = f'memory\\ais_path{count}'

			# Select by MMSI
			exp = f"mmsi = {mmsi_val}"
			sel = SelectLayerByAttribute(ais_pts, 'NEW_SELECTION', exp)

			# Subselect by timestamp date
			texp = (
				f"timestamp >= timestamp '{date_str} 00:00:00' AND "
				f"timestamp < timestamp '{date_str} 23:59:59'"
			)
			ssel = SelectLayerByAttribute(sel, 'SUBSET_SELECTION', texp)

			# Skip if selection empty
			if int(GetCount(ssel)[0]) == 0:
				continue

			# Create line
			path = PointsToLine(ssel, l_name, 'mmsi', 'timestamp', 'NO_CLOSE', 'CONTINUOUS', 'BOTH_ENDS', ['timestamp'])
			p_list.append(path)

		arcpy.AddMessage(f"\tCreated {len(p_list)} track lines...")

		# Merge into output feature class
		out_fc = os.path.join(db, 'ais_paths')
		Merge(p_list, out_fc)
		m.addDataFromPath(out_fc)

		arcpy.AddMessage(f"\tMerged paths into: {out_fc}")
		arcpy.AddMessage(f"\tDone.")