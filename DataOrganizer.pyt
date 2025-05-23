import arcpy, os, sys
from datetime import datetime, timedelta, timezone
from arcpy.conversion import *
from arcpy.management import *
from arcpy import da


class Toolbox(object):
	def __init__(self):
		self.label = "Toolbox"
		self.alias = "Data Organizer"
		self.tools = [DATAORG]


class DATAORG(object):
	def __init__(self):
		"""Compiles and interpolates datasets to identify and symbolize critial data"""
		self.catagory = 'Analysis'
		self.name = 'Data_Organizer',
		self.label = 'Data Organizer'
		self.alias = 'Data_Organizer',
		self.description = "Compiles csv data to identify and symbolize critical data.\
				   \nProject Folder: Path 1\
				   \nArc Project: Path 2\
				   \nProduct Folder: Path 3"
		self.canRunInBackground = False

	def getParamterInfo(self):
		pdata = [
			['Geodatabase Name (Mmm_YY)', 'geodb', 'GPString', 'Required', 'Input', None],
			['.CSV Directory', 'folder', 'GPString', 'Required', 'Input', None]
		]

		params = [
			arcpy.Parameter(
				displayName=d[0],
				name=d[1],
				datatype=d[2],
				parameterType=d[3],
				direction=d[4],
				category=d[5]) for d in [p for p in pdata]]
	
	def isLicensed(self):
		return True

	def updateParameters(self, parameters):
		return True

	def updateMessages(self, parameters):
		return True

		
	def execute(self, parameters, messages):
		arcpy.env.overwriteOutput = True
		
		arcpy.SetLogMetadata(False)
		arcpy.SetLogHistory(False)

		geodb = parameters[0].valueAsText + ".gdb"
		raw_data = parameters[1].valueAsText + "\\"

		# Define Arc Workspace
		gdb_fold = Project Folder Path
		p = arcpy.mp.ArcGISProject('CURRENT')
		gdb = CreateFileGDB(gdb_fold, geodb)
		p.defaultGeodatabase = gdb
		m = p.activeMap
		arcpy.env.workspace = d.defaultGeodatabase
		ws = arcpy.env.workspace
		arcpy.AddMessage(f"{geodb} has been set as the Default Geodatabase!")

		# Define Saptial Reference for the project
		ref = arcpy.SpatialReference(4326)

		ellipse_sym = []   # Empty list for Ellipse Symbology 
		sym_list = []      # Empty list for Point Symbology
		merge_list = []    # Empty list for data type 1
		s_list = []        # Empty list for data type 2

		# Create Ellipse Data (Complete)
		ellipse_list = ['Ellipse 1', 'Ellipse 2']
		ellipse_color = {'RGB' : [169, 0, 230, 25]}, {'RGB' : [230, 152, 0, 25]}, {'RGB' : [76, 230, 0, 25]}
		ellipse_outline = {'RGB' : [169, 0, 230, 100]}, {'RGB' : [230, 152, 0, 100]}, {'RGB' : [76, 230, 0, 100]}
		count = 0
		arcpy.SetProgressor('default', 'Converting CSV data...')
		arcpy.AddMessage(f'Creating Ellipse Feature Class...')
		for e in ellipse_list:
			try:
				# Create editable tables for ellipse csv's
				table = MakeTableView(raw_data + e + ".csv", e) # create table from csv
				new_table = ExportTable(table, e) # export table to GDB
				major = CalculateField(new_table, 'SEMI_MAJOR', '!SEMI_MAJOR!*2', 'PYTHON3') # Calculate Semi Major Field
				minor = CalculateField(new_table, 'SEMI_MINOR', '!SEMI_MINOR!*2', 'PYTHON3') # Calculate Semi Minor Field
				# Create Ellipses from CSV data
				table_ellipse = TableToEllipse(new_table, e + "_p", 'LON', "LAT", "SEMI_MAJOR", "SEMI_MINOR, "NAUTICAL_MILES", "ORIENTATION", "DEGREES", 								attributes=True, geometery_type="POLYGON")
				poly_fc = m.addDataFromPath(table_ellipse)
				arcpy.AddMessage(f"\t{e} added to project...")
				ellipse_sym.append(poly_fc)
				arcpy.AddMessage(f"\t\tSymbolizing Ellipse Vectors...")
				for lyr in ellipse_sym:
					sym_lyr.symbology
					sym.updateRenderer('UniqueValueRenderer')
					sym.renderer.fields = ['Name']
					count_s = 0
					for grp in sym.renderer.groups:
						for itm in grp.items # Find and symboize labels to specific color and alpha
							value = item.values[0][0]
							itm.symbol.color = ellipse_color[count_s]
							itm.symbol.outlineColor = ellipse_outline[count_s]
							if value == "Name 5":
								itm.symbol.outlineColor = ellipse_outline[5]
								itm.symbol.color = ellipse_color[5]
							itm.symbol.outlineWidth = 1.0
							if value == '<Null>':
								itm.label = 'Generic'
							count_s = count_s + 1
					lyr.symbology = sym
			except Exception:
				arcpy.AddMessage(f"\t{e} was not an acceptable input")
			count = count + 1

		# Create Point Data
		# Define .csv file name
		data_list = ['Data1', 'Data2', 'Data3', 'Data4', 'Data5']
		field_val = ['Name1', 'Name2', 'Name3', 'Name4', 'Name5']
		count = 0
		arcpy.SetProgressor('default', 'Converting CSV data...')
		arcpy.AddMessage(f'Creating Point Vector Feature Class...')
		for d in data_list:
			try:
				table_point = XYTableToPoint(raw_data + d + ".csv", d, "LON", "LAT", None, ref)
				if count < 5 or count == 13:
					point_fc = m.addDataFromPath(table_point)
					sym_list.append(point_fc)
				arcpy.AddMessage(f"\t{count}. {d} added to project!")
				if count > 4 and not count == 13:
					AddField(table_point), "Type", "TEXT", field_length=25)
					CalculateField(table_point, "Type", f"'{field_val[count]}'", 'PYTHON3')
					arcpy.AddMessage(f"\t\t{field_val[count]} value was added to {d} 'Type' field..."
					if count > 4 and count < 13:
						merge_list.append(table_point)
					if count > 13:
						s_list.append(table_point)
			except Exception:
				arcpy.AddMessage(f"\t{d} was not an acceptable input...")
			count = count + 1

		# Apply Point Symbology
		s_count = 0
		arcpy.AddMessage(f"\tSymbolizing Point Vectors...")
		for lyr in sym_list:
			sym = lyr.symbology
			sym.updateRenderer('SimpleRenderer')

			gallery_list = ['Circle 3 (40%), "Unknown", "Tent", "Airplane", "Truck"]
			# Apply Symbology from Galary
			sym.renderer.symbol.applySymbolFromGallery(gallery_list[s_count])
			if s_count == 0: # Apply point size for Circle 40%
				sym.renderer.symbol.size = 6
			if s_count == 1: # Apply point size and color for Unknown
				sym.renderer.symbol.color = {'RGB' : [230, 0, 0, 100]} # Red
				sym.renderer.symbol.size = 12
			if s_count == 2: # Apply color and size for Tents
				sym.renderer.symbol.color = {'RGB' : [0, 0, 0, 100]} # Black
				sym.renderer.symbol.size = 12
			if s_count == 3 or s_count == 4:
				sym.renderer.symbol.size = 12
			s_count = s_count + 1 
			lyr.symbology = sym

		# Merge Vectors
		arcpy.SetProgressor('default', 'Merging Vector Data...')
		arcpy.AddMessage(f'Merging Vectors...')
		list_merge = [merge_list, s_list]
		count = 0
		m_s = []
		for c in list_merge:
			if count == 1:
				merge_name = "GOB" + parameters[0].valueAsText + "_T"
			else:
				merge_name = "GOB" + parameters[0].valueAsText
			merge = Merge(c, merge_name)
			m_layer = m.adddataFromPath(merge)
			m_s.append(m_layer)
			count = count + 1
		# Apply Symbology to merged feature
		for lyer in m_s:
			arcpy.AddMessage(f'\tGOB has been merged...')
			arcpy.AddMessage(f'\t\tApplying Symbology to GOB Dataset...')
			sym = lyr.symbology
			sym.updateRenderer('UniqueValueRenderer') # Use Unique Values for Symbology
			sym.renderer.fields = ['Type'] # Access field in VAT
			val_name = ['Air Defense', 'Aircraft', 'APC', 'Artillery', 'Structure', 'Tank', 'Technical', 'Vessel']
			gallery_list = ['Air Defense', 'Aircraft', 'APC', 'Artillery', 'Structure', 'Tank', 'Technical', 'Vessel']
			# Apply Symbology From Gallery
			m_count = 0
			for grp in sym.renderer.groups:
				for item in grp.items:
					value = item.values[0][0]
					if value == val_name[m_count]:
						item.symbol.applySymbolFromGallery(gallery_list[m_count])
					if value == val_name[5]:
						item.symbol.applySymbolFromGallery('Tank')
					if value == 'Structure' # Apply color and size for Tent
						item.symbol.applySymbolFromGallery('Tent')
						item.symbol.color = {'RGB' : [0, 0, 0, 100]} # Black
					if value == 'Vessel':
						item.symbol.applySymbolFromGallery('Tug')
					item.symbol.size = 15
					m_count = m_count + 1
			lyr.symbology = sym
			arcpy.AddMessage(f"\t\tSymbology applied to GOB Dataset")
			
			# Create Date Field Type for Temporal data use
			t_count = 0
			arcpy.AddMessage(f"Formatting Time in Rows...")
			time_list = ['DATE', 'dtg', 'DATE_TIME']
			for lyrs in m.list.Layers()[0:9]:
				ConvertTimeField(lyrs, time_list[t_count], "yyyy/MM/dd HH:mm:ss;AM;PM", "Date", "DATE")
				t_count += 1
			arcpy.AddMessage(f"\tDate Type format was added to feature classses...")
			
			# Group Layers
			# Group layers into Group1 and Group 2
			arcpy.SetProgressor('default', 'Grouping Layers...')
			arcpy.AddMessage(f'Creating Groups for KML creation...')
			group_layers = {
				"Data_1" : ["Group1", "GOB" + parameters[0].valueAsText, sym_list],
				"Data_2" : ["Group2", "GOB" + parameters[0].valueAsText + "2"]
			}
			count = 0
			e_count = 9  # index for group start position
			for group_name, layers in group_layers.items()
				group = m.createGroupLayer(group_layers.keys()) # Create Empty Group
				group.name = group_name
				m.moveLayer(m.listLayers()[e_count], group, 'AFTER') # Move layer below existing layers but above basemap layer
				for lyr in m.listLayers()[0:9]: # layers added to group - skips basemap layer
					if e_count == 9: # adds layers to Group 1
						if lyr.name == "Data1" or lyr.name == "Data2" or lyr.name == "Data3":
							m.addlayerToGroup(group, lyr)
							arcpy.AddMessage(f"\t{lyr.name} added to {group.name} group")
					if e_count == 10: # adds layers to Group 2
						if lyr.name == "Data4" or lyr.name == "Data5":
							m.addLayerToGroup(group, lyr)
							arcpy.AddMessage(f"\t{lyr.name} added to {group.name} group")
				e_count += 1

			# Layer to KML
			arcpy.SetProgressor('default', 'Creating KML...')
			arcpy.AddMessage('Createing KMLs...)
			kml_out = (C:\\...) #hardcode path or create folder in project to store output.
			LayerToKML(g, kml_out)
			arcpy.AddMessage(f"\t{g}.kmz has been created and moved to final folder!")
			
