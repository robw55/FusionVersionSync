# FusionVersionSync
auto sync the Fusion360 cloud version number and display on your part

DESCRIPTION
When iterating on a design you ofter need to make adjustments and try it out.  Ultimatly you end up with multiple parts to compare and you are not certain the version of each part.  You can hard code a version number to be displayed on your part but you will forget one time and now you are worse off.  

This Fusion360 Add-In will automatically update a parametric user paramenter so as you interate on your design, the version number displayed will match the the version in your fusion coud repository.



INSTALLATION
Create a new Fusion Add-In
1.	Create a folder at C:\Users\<USERNAME>\AppData\Roaming\Autodesk\Autodesk Fusion 360\API\AddIns  called FusionVersionSync.

2.	Create a python file called FusionVersionSync.py and place the python code inside.

3.	Create a file called manifest.json and copy the manifest code into it.

4.	Restart Fusion360 so it loads in the new Add-In.

5.	In the top level menu click Utilities then click the Add-Ins menu item.  You should see the new FusionVersion add-in. You will need to click the run button to start it. If you want it automatically started everytime you use Fusion, click the checkbox in the run on startup column.
	
	

HOW TO USE
1.	Open the user parameters Fx menu.

2.	Add a new user parameter called FusionVersion and initially set it to 0.

3.	Inside any sketch add a text element. Without the '' enter FusionVersion.  Optionally you can enter 'V' + FusionVersion and it will displlay V4 for example.
	
4. When you are finished with your design you can remove that text element from your sketch.
