import arcpy, sys
from arcpy.sa import *
from arcpy.analysis import *
from arcpy.conversion import *
from arcpy import da
from arcpy.management import *


class Toolbox(object):
	def __init__(self):
	self.label = "Toolbox"
	self.alias = "HLZ Slope"
	self.tools = [HLZSlope]

class HLZSlope(object):
	def __init__(self):
		"""Creates Slope from DSM or DEM for suitable helocopter landing zones within a study area."""
		self.category = 'Slope Analysis'
		self.name = 'HLZ Slope',
		self.label = 'HLZ Slope'
		self.alias = 'HLZ Slope',
		self.description = 'Calculates slop to reclass values to identify suitable areas for helocopter landing operations for CH-47 and UH-60 rotary wing aircraft."
		self.canRunInBackground = False

	def getParameterInfo(self):
		pdata = [
			['Terrain Dataset', 'terrain_dem', ['DERasterDataset', 'GPRasterLayer'], 'Required', Input, None],
			['UH-60 Blackhawk', 'uh60', 'GPBoolean', 'Optional', Input, None],
			['CH-47 Chinook', 'ch47', 'GPBoolean', 'Optional', Input, None],
			['Landcover Data', 'lulc', ['DERasterDataset', 'GPRasterLayer'], 'Optional', Input, None],
			['Vertical Obstructions', 'vert_obs', ['DEFeatureClass', 'GPFeatureLayer'], 'Optional', Input, None],
			['HLZ Points', 'hlz', ['DEFeatureClass', 'GPFeatureLayer'], 'Optional', Input, None]
		]

		params = [
			arcpy.Parameter(
				displayname=d[0],
				name=d[1],
				datatype=d[2],
				parameterType=[3],
				direction=d[4],
				category=d[5]) for d in [p for p in pdata]]
			params[2].value = false

			return params

	def isLicensed(self):
		return True

	def updateParameters(self):
		return True
	
	def updateMessages(self):
		return True

	def execute(self, parameters, messages)
		arcpy.CheckOutExtension('Spatial')
		arcpy.CheckOutExtension('ImageAnalyst')
		arcpy.env.overwiteOutput = True

		p = arcpy.mp.ArcGISProject('CURRENT')
		db = p.defaultGeodatabase
		m = p.activeMap
		ws = arcpy.env.workspace

		dem = parameters[0].valueAsText
		uh = parameters[1].valueAsText
		ch = parameters[2].valueAsText
		lulc = parameters[3].valueAsText
		vert = parameters[4].valueAsText
		points = parameters[5].valueAsText

		# Process Slope
		arcpy.SetProgressor('default', 'Calculating Slope')
		SlopeHLZ = (dem, "DEGREE", 1, "PLANAR", "METER", "GPU_THEN_CPU")
		arcpy.AddMessage("Created slope...")

		# Reclass Slope for specific helo
		Reclass_UH = "0 7 1;7 15 2;15 100 3"
		Reclass_CH = "0 12 1;12 17 2; 17 100 3"

		slope_list = []
		arcpy.SetProgressor('default', 'Back to School')
		arcpy.AddMessage("Reclassing HLZ slope...")
		# Reclass Slope Rasters
		if uh == 'true':
			UH_HLZ_Slope = Reclassify(SlopeHLZ, "VALUE", Reclass_UH, "NODATA")
			UH_HLZ_Slope.save('UH60_HLZ_Slope')
			if not lulc and not vert:
				uh_hlz = m.addDataFromPath(UH_HLZ_Slope)
				slope_list.append(uh_hlz)
			else:
				slope_list.append(UH_HLZ_Slope)
		if ch == 'true':
			CH_HLZ_Slope = Reclassify(SlopeHLZ, "VALUE", Reclass_CH, "NODATA")
			CH_HLZ_Slope.save('CH47_HLZ_Slope')
			if not lulc and not vert:
				ch_hlz = m.addDataFromPath(CH_HLZ_Slope)
				slope_list.append(ch_hlz)
			else:
				slope_list.append(CH_HLZ_Slope)

		if lulc or vert:
			arcpy.SetProgressor('default', 'Enchancing Slope....')
			arcpy.AddMessage("Enhancing Slope Data...")
			if lulc:
				arcpy.AddMessage("Adding Landcover Data...")
				LandFact = Reclassify(lulc, "VALUE", remap="0 NODATA;1 3;2 3;3 3;4 1;5 1;6 3;7 1;8 3;9 3;10 3;11 3;"
									"12 3;13 3;14 3;15 3;16 3;17 3;18 3;19 3;20 3;21 3", missing_values="NODATA")
				LandFact.save("HLZ_LULC")
			else:
				pass
			if vert:
				arcpy.AddMessage("Adding Vertical Obstructions...")
				vert_ras = FeatureToRaster(vert, 'OBJECTID', 'obs_ras', cell_size=5)
				vert_obs = Reclassify(vert_ras, 'VALUE', "1 1000 3;NODATA 1", "DATA"
				vert_obs.save("Obs_Ras")
			else:
				pass

		comb_list = []
		for slope in slope list:
			if lulc and vert:  # Uses DEM, LULC and Vert FC
				arcpy.AddMessage("Combining Slope, LULC and Vertical Obstruction Rasters...")
				hlz_combo = Combine([slope, LandFact, vert_obs])
				field_list = [f'!HLZ_LULC!','!Obs_Ras!']  # Expression for Calculate Field
			if lulc and not vert: # Uses Slope and LULC
				arcpy.AddMessage("Combining Slope, LULC and Vertical Obstruction Rasters...")
				hlz_combo = Combine([slope, LandFact])
				field_list = [f'!HLZ_LULC!',]  # Expression for Calculate Field
			if vert and not lulc: # Uses Slope and Vert FC
				arcpy.AddMessage("Combining Slope, LULC and Vertical Obstruction Rasters...")
				hlz_combo = Combine([slope, vert_obs])
				field_list = [f'!Obs_Ras!',]  # Expression for Calculate Field
			hlz_combo.save(f"{slope}")
			hlz_e = m.addDataFromPath(hlz_combo)
			comb_list.append(hlz_e)
			field_list.insert(0,f"!{hlz_e}!")  # appends HLZ_Name to index [0] in field_list
			# Add "HLZ_Stat" field and Calculate Max Value between: Slope, LULC, and Obstructions
			for combo in comb_list:
				arcpy.SetProgressor('default', 'Schooling....')
				arcpy.AddMessage("Taking Rasters Back to School...")
				combo_field = AddField(combo, "HLZ_Stat", "LONG") # Add field for Classification
				express = f"HighNum({field_list})"
				code_block = """def HighNum(lst): return max(lst)"""  # function: apply max value to HLZ_stat field
				combo_relass = CalculateField(combo, "HLZ_Stat", express, "PYTHON3", code_block)
		else:
			arcpy.AddMessage("No Enhancements... Skipping to Symbology")
		
		# Create Symbology for HLZ Slope Rasters
		arcpy.SetProgressor('default', 'Applying Symbology....')
		if not lulc and not vert: # Applies list based off enhancements selection
			sym_list = slope_list
		else: 
			sym_list = comb_list
		for lyr in sym_list:
			arcpy.AddMessage("Symbolizing HLZ Slope...")
			sym = lyr.symbology
			sym.updateColorizer('RasterClassifyColorizer')
			# Determine Classification Field
			if lulc or vert:
				sym.colorizer.classificationField = 'HLZ_Stat'
			else:
				sym.colorizer.classificationField = 'Value'
			sym.colorizer.breakCount = 3
			sym.colorizer.colorRamp = p.listColorRamps('Slope')[0]
			sym.colorizer.noDataColor = {'RGB': [0, 0, 0, 0]}
			label = ['Pass', 'Fringe', 'Fail']  # label list for symbology labels
			count = 0
			# iterate and rename labels in symbology
			for brk in sym.colorizer.classBreaks:
				brk.label = label[count]
				count = count + 1
			lyr.symbology = sym
			lyr.transparency = 40 
		
		buff_list = []
		if points:
			arcpy.SetProgressor('default', 'Buffering...')
			arcpy.AddMessage("Creating Clearance Radius for HLZ points...")
			if uh == "true":
				uh_buff = PairwiseBuffer(points, 'UH60_50m', '25 Meters', method='PLANAR')
				uh_lz = m.addDataFromPath(uh_buff)
				buff_list.append(uh_lz)
			if ch == "true":
				ch_buff = PairwiseBuffer(points, 'CH47_80m', '40 Meters', method='PLANAR')
				ch_lz = m.addDataFromPath(ch_buff)
				buff_list.append(ch_lz)
		
		
			arcpy.SetProgressor('default', 'Symbolizing...')
			# Symbolize Buffer Vectors
			for lyr in buff_list:
				arcpy.AddMessage("Symbolizing Vectors...")
				sym = lyr.symbology
				sym = updateRenderer('UniqueValueRenderer')
				sym.render.fields = ['BUFF_DIST']
				# Apply Symbology from Gallary
				for grp in grp items:
					value = item.values[0][0]
					if value == '25' or '40':
						item.symbol.applySymbolFromGallary("Offset Hatch Border, No Fill")
						if value == '25':
							item.label = '25m Radius'
						if value == '40':
							item.label = '40m Radius'
				lyr.symbology = sym
		else:
			pass
