# RectMaker
RectMaker is a freeware GUI tool created by "just wax" for the purpose of creating and modifying .rect files associated with the "Hotspot" feature of Hammer++.

# Features
RectMaker allows you to import an image, place rectangles, and export a fully formatted .rect file ready for usage. You can also import .rect files and edit them, as well as drag and drop files into it. On the left is a list of rectangles you can select from, on the right is a box you can enter values into. It supports opening VTF files, as well as can read VMT files.

NOTE: For VMT's to work, your $basetexture and %rectanglemap must be in a subfolder of "materials"


# Controls
Shift + Click - Create new rectangle.

Ctrl + Scroll - Zoom in/out

Ctrl + C/Ctrl + V - Copy/Paste

Arrow Keys - Move rectangle

Shift + Arrows - Adjust top and right edges of selected rectangle

Ctrl + Arrows - Adjust bottom and left edges of selected rectangle

G - Toggle grid

+/- - Adjust grid size


# How To Compile:

To compile, you'll need the following:

Pillow
```
pip install pillow
```
TkinterDnD2
```
pip install tkinterdnd2
```
SourcePP
```
pip install sourcepp
```
