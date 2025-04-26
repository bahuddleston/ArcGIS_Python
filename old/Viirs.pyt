import arcpy, os
from arcpy.sa import *
from arcpy.management import *
from arcpy.conversion import *
from arcpy.analysis import *
from arcpy.cartography import *
import arcpy.mp
from arcpy.edit import *


class Toolbox(object):
	def __init__(self):
		self.label = "Toolbox"
		self.alias = "VIIRS"
		self.tools = [Viirs]

class Viirs(object):
	def __init__(self):
		"""Symbolizes VIIRS Data and creates points/poly vectors for distribution."""
		self.category = 'Analysis'
		self.name = 'VIIRS_Symbols'
		self.label = 'VIIRS Bright Lights'
		self.alias = 'VIIRS Bright Lights'
		self.description = 'Symbolizes VIIRS Data and creates points/poly vectors for distribution.'
		self.canRunInBackground = False

	def getParameterInfo(self):
		pdata = [
			['VIIRS Dataset', 'vd', ['DERasterDataset', 'GPRasterLayer'], 'Required', 'Input', None, True],
			['Polygon Vectors', 'polygon', 'GPBoolean', 'Optional', 'Input', 'Advanced Options', False],
			['Point Vector', 'point', 'GPBoolean', 'Optional', 'Input', 'Advanced Options', False],
			['Processing area', 'processing_area', 'GPString', 'Required', 'Input', None, False]
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
		params[3].filter.type = 'ValueList'
		params[3].filter.list = ['View Extent', 'Dataset extent']
		params[3].value = 'View Extent'
		return params

	def isLicensed(self):
		return True

	def updateParameters(self, parameters):
		if parameters[1].value == True:
			parameters[2].enabled = True
		else:
			parameters[2].enabled = False
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
		arcpy.CheckOutExtension('Spatial')
		arcpy.env.overwriteOutput = True

		p = arcpy.mp.ArcGISProject('CURRENT')
		db = p.defaultGeodatabase
		m = p.activeMap
		ws = arcpy.env.workspace

		viirs = parameters[0].valueAsText.split(';')
		pv = parameters[1].value
		pts = parameters[2].value
		proc_area = parameters[3].valueAsText
		if proc_area == 'View Extent':
			arcpy.env.extent = self.get_view_extent(
				sr=arcpy.Describe(viirs[0]).spatialReference
			)
		else:
			arcpy.env.extent = viirs[0]

		v_list = []
		arcpy.AddMessage('Reclassifying Raster(s)...')
		for v in viirs:
			basename = os.path.basename(v.split('_')[2])
			name = f'VIIRS_{basename[1:9]}'
			output = os.path.join(db, name)
			reclass = Reclassify(v, 'VALUE', remap="-100 3 NODATA;3 7 1;7 10 2;10 13 3;13 15 4;15 20 5;20 23 6;23 25 7;25 10000 8; NODATA 0", missing_values="DATA")
			reclass.save(output)
			v_list.append(reclass)

		# Symbolize
		arcpy.SetProgressor('default', 'Applying symbology...')
		arcpy.AddMessage('Modifying Raster Symbology...')
		for v in v_list:
			lyr = m.addDataFromPath(v)
			lyr.name = arcpy.Describe(v).name
			sym = lyr.symbology
			sym.updateColorizer('RasterStretchColorizer')
			sym.colorizer.stretchType = 'MinimumMaximum'
			sym.colorizer.minLabel = 'Dim'
			sym.colorizer.maxLabel = 'Bright'
			sym.colorizer.colorRamp = p.listColorRamps('Magma')[0]
			sym.colorizer.noDataColor = {'RGB': [0, 0, 0, 0]}
			lyr.symbology = sym
			lyr.transparency = 40

		# Create Bright Light Polygons
		if pv:
			for v in v_list: # iterate raster(s)
				base = str(v)[14:]
				p_name = os.path.basename(base.replace('VIIRS', 'LightSource'))
				if pts: # saves point vectors
					temp = p_name
				else: # stores points and does not save
					temp = f"in_memory/{p_name}"
				sel = SelectLayerByAttribute(v, "NEW_SELECTION", "Value IN (6, 7, 8)") #select high values
				RtP = RasterToPoint(sel, temp, 'Value')
				buff = PairwiseBuffer(RtP, p_name, '300 Meters', 'ALL', method='PLANAR')
				if arcpy.GetInstallInfo()["LicenseLevel"] == "Basic": #Check License for >Basic
					m.addDataFromPath(buff)
					Generalize(buff, '150 Meters')
				else: #Smooth Lines and add data to map
					arcpy.AddMessage("Smoothing Light Source Polygons...")
					smooth = SmoothPolygon(buff, os.path.join(db, p_name + '_sp'), "PAEK", "400 Meters")
					arcpy.AddMessage(f"{p_name} complete...")
					m.addDataFromPath(smooth)
		arcpy.AddMessage(f"VIIRS data complete... ♪~ ᕕ(ᐛ)ᕗ")
