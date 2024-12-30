Centerlines

import arcpy, sys, os
from arcpy.management import *
from arcpy.conversion import *
from arcpy.analysis import *
from arcpy import da
from arcpy.topographic import *
from pathlib import Path


class Tollbox(object):
	def __init__(self):
		self.label = "Toolbox"
		self.alias = "Centerlines"
		self.tools = [SCCDp]

class SCCDp(object):
	def __init__(self):
		"""Input Shapefile from X and filters dates to create center polylines within each polygon"""
		self.catagory = 'Production Events'
		self.name = 'Polygon_Converter',
		self.label = 'Polygon Converter'
		self.alias = 'Polygon Converter',
		self.description = 'Input Shapefile from X and filters dates to create center polylines within each polygon'
		self.canRunInBackground = False

	def getParameterInfo(self):
		pdata = [
			['Input', 'infile', 'DEFeatureClass', 'Required', 'Input', None],
			['Merge Shapefiles?', 'f_merge', 'GPBoolean', 'Optional', 'Input', None]
		]

		params = [
			arcpy.Parameter(
				displayName=d[0],
				name=d[1],
				datatype=d[2],
				parameterType=d[3],
				direction=d[4],
				category=[5]) for d in [p for p in pdata]]
		return params

	def isLicensed(self):
		return True

	def updateParameters(self, parameters):
		return True

	def get_home_path(self):
		p = arcpy.mp.ArcGISProject("CURRENT")
		return Path(p.homeFolder).resolve()

	def execute(self, parameters, messages):
		p = arcpy.mp.ArcGISProject("CURRENT")
		m = p.activeMap
		ws = arcpy.env.workspace
		arcpy.env.overwriteOutput = True

		infile = parameters[0].valueAsText.split(';')
		f_merge = parameters[1].value

		in_list = [infile]
		# create output folder
		outfold = os.path.join(self.get_home_path(), f"Centerlines_shp")
		if not os.path.exists(outfold): os.mardirs(outfold)

		arcpy.AddMessage(f'Begin Centerline Tool...')
		if len(in_list) <= 1: # only one shapefile
			arcpy.AddMessage(f'One shapefile has been detected')
			cd_n = os.path.basename(infile[0])[-37:-4]
			cd = CopyFeatures(infile[0], cd_n)
			scd = m.addDataFromPath(cd)
			arcpy.AddMessage(f'\tCreating Centerlines')
			m_list = []
			values = sorted(list({
				row[0] for row in da.SearchCursor(scd, 'ref_date')
				}))  # searches for dates in shapefiles
			for c in values:
				o_cl = f'in_memory/cd_{c}'
				where_clause = f"ref_date = '{c}'"
				sel = SelectLayerByAttribute(scd, "NEW_SELECTION", where_clause) # select layers by date
				center_l = PolygonToCenterline(sel, o_cl) # create centerlines
				m_list.append(center_l)

		# Merge features or By Day shapefiles and save to Centerlines folder
		if f_merge: # Merge ALL fc to one shapefile
			arcpy.AddMessage(f'\tMerging Centerline Features...')
			merge_n = f'cd_{values[0]}_{values[-1]}' # filename with first and last dates
			merge = Merge(m_list, os.path.join(ws, merge_n))
			m.addDataFromPath(merge)
			join = AddJoin(merge, 'FID', scd, 'OBJECTID', join_operation='JOIN_ONE_TO_FIRST') # join tables to centerline fc
			CopyFeatures(join, os.path.join(outfold, merge_n))  # Save to outfold dir
		else: # Save fc as separate shapefiles
			arcpy.AddMessage(f'\tCreating Centerline Features by Day...')
			for d in m_list: # iterate by day
				d_name = os.path.join(ws, str(d).replace('in_memory\\', ''))  #output dest
				day_t = ExportFeatures(d, d_name) # export to workspace
				day = m.addDataFromPath(day_t)
				join = AddJoin(day, 'FID', scd, 'OBJECTID', join_operation='JOIN_ONE_TO_FIRST') #join tables to centerline fc
				ExportFeatures(join, os.path.join(outfold, os.path.basename(d_name)[-13])) # export to Centerline Folder
		arcpy.AddMessage(f'Centerline Tool is Complete!!!')
		arcpy.AddMessage(f'Shapefiles are saved in {outfold} !!!')
				
