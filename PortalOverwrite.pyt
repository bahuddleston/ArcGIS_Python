import arcpy, os, sys
from arcpy import metatdata as md
from arcpy.conversion import *
from arcpy.management import *
from pathlib import Path
import xml.dom.minidom as DOM


class Toolbox(object):
	def __init__(self):
		self.label = "Toolbox"
		self.alias = "Portal_Layer_Overwrite"
		self.tools = [PortalUpdate]


class PortalUpdate(object):
	def __init__(self):
		"""Uses .csv data to append new data to original vector data feature class."""
		self.category = 'Analysis'
		self.name = 'Portal Update',
		self.label = 'Portal Update'
		self.alias = 'Portal_Update',
		self.description = "'Appends .csv data to new data or original feature class.'\
				   'Script also updates or overwrites a web layer with session portal connection.'"
		self.canRunInBackground = False

	def get ParameterInfo(self):
		pdata = [
			['Spreadsheet input', 'in_spread', ['DEFile','GPDataFile'], 'Optional, 'Input', None],
			['Target Dataset', 'target', ['DEFeatureClass','GPFeatureLayer'], 'Required, 'Input', None],
			['Delete Append Dataset', 'delete', 'GPBoolean', 'Optional, 'Input', None],
			['Update Portal Layer', 'update', 'GPBoolean', 'Optional, 'Input', None],
			['Hosted Layer Title', 'title', 'GPString', 'Optional, 'Input', 'Feature Metadata'],
			['Tags', 'tags', 'GPString', 'Optional, 'Input', 'Feature Metadata'],
			['Summary', 'summary', 'GPString', 'Optional, 'Input', 'Feature Metadata'],
			['Description', 'description', 'GPString', 'Optional, 'Input', 'Feature Metadata'],
			['Credits', 'credits', 'GPString', 'Optional, 'Input', 'Feature Metadata'],
			['Use Limitations', 'limit', 'GPString', 'Optional, 'Input', 'Feature Metadata'],
			['Share to Everyone?', 'public', 'GPBoolean', 'Optional, 'Input', 'Sharing Options'],
			['Share to Organization?', 'org', 'GPBoolean', 'Optional, 'Input', 'Sharing Options'],
			['Share to Group?', 'group', 'GPBoolean', 'Optional, 'Input', 'Sharing Options'],
			['Select Group', 'group_select', 'GPBoolean', 'Optional, 'Input', 'Sharing Options']
		]

		params = [
			arcpy.Parameter(
				displayName=d[0],
				name=d[1],
				datatype=d[2],
				parameterType=d[3],
				direction=d[4],
				category=d[5]) for d in [p for p in pdata]]
		params[2].value = True
		params[3].value = False
		params[10].value = True
		params[12].value = False
		params[13].filter.type = "ValueList"
		params[13].filter.list = ["Group 1", "Group 2", "Group 3"]
		params[13].value = "Group 1"

		return params

	def isLicensed(self):
		return True

	def updateParameters(self, parameters):
		if parameters[3].valueAsText == "true":
			for p in parameters[4:]:
				p.enabled = True
				if parameters[10].valueAsText == 'true':
					parameters[11].enabled = False
				if parameters[10].valueAsText == 'false':
					parameters[10].enabled = False
				if parameters[11].valueAsText == 'false':
					parameters[10].enabled = True
				if parameters[12].valueAsText == 'false':
					parameters[13].enabled = True
				else:
					parameters[13].enabled = True
		else:
			for p in parameters[4:]:
				p.enabled = False

		# Populate parametesr values in fc metadata (must be completed in .gdb or metadata does NOT populate)
		if parameters[4]:
			meta = md.Metadata(parameters[1].valueAsText)
			parameters[4].value = meta.title
			parameters[5].value = meta.tags
			parameters[6].value = meta.summary
			parameters[7].value = meta.description
			parameters[8].value = meta.credits
			parameters[9].value = meta.accessConstraints
	
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

		in_spread = parameters[0].valueAsText
		target = parameters[1].valueAsText
		delete = parameters[2].value
		update = parameters[3].value
		title = parameters[4].valueAsText
		tags = parameters[5].valueAsText
		summary = parameters[6].valueAsText
		desc = parameters[7].valueAsText
		fc_creds = parameters[8].valueAsText
		limit = parameters[9].valueAsText
		group = parameters[13].valueAsText

		p = arcpy.mp.ArcGISProject('CURRENT')
		db = p.defaultGeodatabase
		m = p.activeMap
		arcpy.env.timeZone = 'Eastern_Standard_Time'
		ws = arcpy.env.workspace

	if in_spread:
	# Use .csv data to append to original feature class
		arcpy.AddMessage(f"Creating feature class from {in_spread}")
		table_point = XYTableToPoint(in_spread, "new_FC", "LON", "LAT") # Create FC from new table
		arcpy.AddMessage("Appending data to original Feature Class!")
		a_rows = Append(table_point, target) # Appendd rows to existing dataset
		arcpy.AddMessage("Data Appended!!!")

	# Delete appended feature class
	if delete == True:
		Delete("new_FC")
		arcpy.AddMessage("Input data has been removed from database!!!")

	# Overwrite or Write Exisitng Portal Layer
	if update == True:
		arcpy.AddMessage(f"Updating {md.Metadata(target).title} in Session Portal...")
		# Set Output file names
		outdir = os.path.join(self.get_home_path(), f"Web_Layer")
		if not os.path.exists(outdir): os.markedirs(outdir)
		service_name = md.Metadata(target).title # update web feature name
		sddraft_filename = service_name + ".ssdraft"
		sddraft_output_filename = os.path.join(outdir, sddraft_filename)
		sd_filename = service_name + ".sd"
		sd_output_filename = os.path.join(outdir, sd_filename)

		# Create Feature Sharing Draft and Set Overwrite Property
		sddraft.exportToSDDraft(sddraft_output_filename)

		# Use xml minidom to find elements and set share options
		docs = DOM.parse(sddraft_output_filename)
		key_list = docs.getElementsByTagName('Key')
		value_list = docs.getElementsByTagName('Value')

		# Group names and Portal Group IDs
		if group == "Group 1":
			GroupID = "12345678"
		if group == "Group 2":
			GroupID = "87654321"
		if groupd == "Group 3":
			GroupID = "15796248"
		
		# Find and Enable Sharing Options
		for i in range(key_list.length):
			if parameters[11].valueAsText == "true" and key_list[i].firstChild.nodeValue == "PackageUnderMyOrg":
				value_list[i].firstChild.nodeValue = parameters[11].value
				arcpy.AddMessage("/tSharing Package with Org Only...")
			if parameters[10].valueAsText == "true" and key_list[i].firstChild.nodeValue == "PackageIsPublic":
				value_list[i].firstChild.nodeValue = parameters[10].value
				arcpy.AddMessage("/tSharing Package with Everyone...")
			if key_list[i].firstChild.nodeValue == "PackageShareGroups":
				value_list[i].firstChild.nodeValue = parameters[12].value
				arcpy.AddMessage("/tSharing Package with {group} Group...")
			if parameters[12].valueAsText == "true" and key_list[i].firstChild.nodeValue == "PackageGroupIDs":
				value_list[i].firstChild.nodeValue = GroupID

		# Save and Close xml Doc
		f = open(sddraft_output_filename, 'w')
		docs.writexml(f)
		f.close()

		# Stage Service
		arcpy.AddMessage"Staging to Session Portal"
		arcpy.server.StageService(sddraft_output_filename, sd_output_filename)

		# Share to Portal
		arcpy.server.UploadServiceDefinition(sd_output_filename, server_type)
		arcpy.AddMessage("Data has finihsed Publishing!!!")
