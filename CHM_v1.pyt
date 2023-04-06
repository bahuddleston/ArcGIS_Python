import arcpy
import arcpy.sa
import arcpy.management
import os


class Toolbox(object):
    def __init__(self):
        self.label = "Toolbox"
        self.alias = "AglTool"
        self.tools = [Agl]


class Agl(object):
    def __init__(self):
        """Define the tool (tool name is the class name)"""
        self.label = "Agl"
        self.description = "Calculates the difference between two input rasters and converts the result to a " \
                           "16-bit image with user specified resolution."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        params0 = arcpy.Parameter(
            displayName="Input DSM",
            name="in_raster_1",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        params1 = arcpy.Parameter(
            displayName="Input Base DEM",
            name="in_raster_2",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        params2 = arcpy.Parameter(
            displayName="Output Raster",
            name="out_raster",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Output")

        params3 = arcpy.Parameter(
            displayName="Resolution Meters Increments",
            name="res_options",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        params3.filter.type = "ValueList"
        params3.filter.list = ['3m_rural', '3m_urban', '5m', 'N/A']


        params4 = arcpy.Parameter(
            displayName="Create Feet Classification (Optional)",
            name="Output Dimensions",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        params4.value = True

        params5 = arcpy.Parameter(
            displayName="Resolution Feet Increments",
            name="res_options",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        params5.filter.type = "ValueList"
        params5.filter.list = ['9ft_rural', '9ft_urban', '15ft', 'N/A']
        return [params0, params1, params2, params3, params4, params5]

    def execute(self, parameters, messages):
        """Execute the tool logic"""
        arcpy.env.overwriteOutput = True
        aprx = arcpy.mp.ArcGISProject('current').activeMap
        fgdb = arcpy.env.workspace
        params0 = parameters[0].valueAsText
        params1 = parameters[1].valueAsText
        params2 = parameters[2].valueAsText
        params3 = parameters[3].valueAsText
        params4 = parameters[4].valueAsText
        params5 = parameters[5].valueAsText

        arcpy.AddMessage("\tBeginning Raster Calculations")
        calculations = arcpy.sa.Raster(params0) - arcpy.sa.Raster(params1)  # subtract DSM from DEM raster
        arcpy.AddMessage(arcpy.GetMessages())

        arcpy.AddMessage("\tRemoving Elevation <2m with Con statement")
        agl_con = arcpy.ia.Con(calculations >= 2, calculations)  # con to remove elevation below 2 meters
        arcpy.AddMessage(arcpy.GetMessages())

        arcpy.AddMessage("\tConverting Raster to 16-bit")
        meter_ras = arcpy.CopyRaster_management(agl_con, params2, pixel_type="16_BIT_UNSIGNED")
        arcpy.AddMessage(arcpy.GetMessages())

        # Change the resolution of the result raster
        if params4 == 'true' or 'false':
            if params3 == "3m_rural":
                with arcpy.EnvManager(cellSize="MINOF"):
                    arcpy.AddMessage("\nReclassing Data - 3m Increments")
                    final_raster = arcpy.sa.Reclassify(in_raster=meter_ras, reclass_field="VALUE", remap="2 3 3;3 6 6;"
                                                                                                         "6 9 9;9 12 12"
                                                                                                         ";12 15 15;"
                                                                                                         "15 18 18;"
                                                                                                         "18 21 21;"
                                                                                                         "21 24 24;"
                                                                                                         "24 27 27;"
                                                                                                         "27 30 30;"
                                                                                                         "30 100000 30",
                                                                                                         missing_values=
                                                                                                         "NODATA")
                    arcpy.AddMessage(arcpy.GetMessages())
                    final_raster.save("AGL_3m_rural")
                    to_map = fgdb + "/AGL_" + params3
                    aprx.addDataFromPath(to_map)
            if params3 == "3m_urban":
                with arcpy.EnvManager(cellSize="MINOF"):
                    arcpy.AddMessage("\nReclassing Data - 3m Increments")
                    final_raster = arcpy.sa.Reclassify(in_raster=meter_ras, reclass_field="VALUE", remap="2 3 3;"
                                                                                                         "3 6 6;"
                                                                                                         "6 9 9;"
                                                                                                         "9 12 12"
                                                                                                         ";12 15 15;"
                                                                                                         "15 18 18;"
                                                                                                         "18 21 21;"
                                                                                                         "21 24 24;"
                                                                                                         "24 27 27;"
                                                                                                         "27 30 30;"
                                                                                                         "30 33 33;"
                                                                                                         "33 36 36;"
                                                                                                         "36 39 39;"
                                                                                                         "39 42 42;"
                                                                                                         "42 45 45;"
                                                                                                         "45 48 48;"
                                                                                                         "48 51 51;"
                                                                                                         "51 54 54;"
                                                                                                         "54 57 57;"
                                                                                                         "57 60 60;"
                                                                                                         "60 100000 "
                                                                                                         "60",
                                                                                                         missing_values=
                                                                                                         "NODATA")
                    arcpy.AddMessage(arcpy.GetMessages())
                    final_raster.save("AGL_3m_urban")
                    to_map = fgdb + "/AGL_" + params3
                    aprx.addDataFromPath(to_map)
            if params3 == "5m":
                with arcpy.EnvManager(cellSize="MINOF"):
                    arcpy.AddMessage("\nReclassing Data - 5m Increments")
                    final_raster = arcpy.sa.Reclassify(in_raster=meter_ras, reclass_field="VALUE", remap="2 5 5;"
                                                                                                         "5 10 10;"
                                                                                                         "10 15 15;"
                                                                                                         "15 20 20"
                                                                                                         ";20 25 25;"
                                                                                                         "25 30 30;"
                                                                                                         "30 35 35;"
                                                                                                         "35 40 40;"
                                                                                                         "40 45 45;"
                                                                                                         "45 50 50;"
                                                                                                         "50 100000 "
                                                                                                         "50",
                                                                                                         missing_values=
                                                                                                         "NODATA")
                    arcpy.AddMessage(arcpy.GetMessages())
                    final_raster.save("AGL_5m")
                    to_map = fgdb + "/AGL_" + params3
                    aprx.addDataFromPath(to_map)
            if params3 == "N/A":
                pass
        if params4 == 'true':
            arcpy.AddMessage("\tConverting Meters to Feet")
            feet_ras = arcpy.sa.Times(meter_ras, 3.2808399)  # converts meters to feet
            feet_ras.save("Agl_ft")
            arcpy.AddMessage(arcpy.GetMessages())
            if params5 == '9ft_rural':
                with arcpy.EnvManager(cellSize="MINOF"):
                    arcpy.AddMessage("\nReclassing Data - 9ft Increments")
                    final_raster = arcpy.sa.Reclassify(in_raster=feet_ras, reclass_field="VALUE", remap="6 9 9;"
                                                                                                        "9 18 18;"
                                                                                                        "18 27 27;"
                                                                                                        "27 36 36"
                                                                                                        ";36 45 45;"
                                                                                                        "45 54 54;"
                                                                                                        "54 63 63;"
                                                                                                        "63 72 72;"
                                                                                                        "72 81 81;"
                                                                                                        "81 90 90;"
                                                                                                        "90 100000 90",
                                                                                                        missing_values=
                                                                                                        "NODATA")
                    arcpy.AddMessage(arcpy.GetMessages())
                    final_raster.save("AGL_9ft_rural")
                    to_map = fgdb + "/AGL_" + params5
                    aprx.addDataFromPath(to_map)
            if params5 == '9ft_urban':
                with arcpy.EnvManager(cellSize="MINOF"):
                    arcpy.AddMessage("\nReclassing Data - 9ft Increments")
                    final_raster = arcpy.sa.Reclassify(in_raster=feet_ras, reclass_field="VALUE", remap="6 9 9;"
                                                                                                        "9 18 18;"
                                                                                                        "18 27 27;"
                                                                                                        "27 36 36"
                                                                                                        ";36 45 45;"
                                                                                                        "45 54 54;"
                                                                                                        "54 63 63;"
                                                                                                        "63 72 72;"
                                                                                                        "72 81 81;"
                                                                                                        "81 90 90;"
                                                                                                        "90 99 99;"
                                                                                                        "99 108 108;"
                                                                                                        "108 117 117;"
                                                                                                        "117 126 126;"
                                                                                                        "126 135 135;"
                                                                                                        "135 144 144;"
                                                                                                        "144 153 153;"
                                                                                                        "153 162 162;"
                                                                                                        "162 171 171;"
                                                                                                        "171 180 180;"
                                                                                                        "180 100000 180",
                                                                                                        missing_values=
                                                                                                        "NODATA")
                    arcpy.AddMessage(arcpy.GetMessages())
                    final_raster.save("AGL_9ft_urban")
                    to_map = fgdb + "/AGL_" + params5
                    aprx.addDataFromPath(to_map)
            if params5 == '15ft':
                with arcpy.EnvManager(cellSize="MINOF"):
                    arcpy.AddMessage("\nReclassing Data - 15ft Increments")
                    final_raster = arcpy.sa.Reclassify(in_raster=feet_ras, reclass_field="VALUE", remap="6 15 15;"
                                                                                                        "15 30 30;"
                                                                                                        "30 45 45;"
                                                                                                        "45 60 60"
                                                                                                        ";60 75 75;"
                                                                                                        "75 90 90;"
                                                                                                        "90 105 105;"
                                                                                                        "105 120 120;"
                                                                                                        "120 135 135;"
                                                                                                        "135 150 150;"
                                                                                                        "150 100000 "
                                                                                                        "150",
                                                                                                        missing_values=
                                                                                                        "NODATA")
                    arcpy.AddMessage(arcpy.GetMessages())
                    final_raster.save("AGL_15ft")
                    to_map = fgdb + "/AGL_" + params5
                    aprx.addDataFromPath(to_map)
        if params5 == "N/A":
            pass